import os
import subprocess
import yaml


class Logger(object):
    def set_verbose(self,verbose=True):
        self._verbose = verbose

    def log(self, message):
        print(message)

    def log_verbose(self, message):
        if not self._verbose:
            return
        self.log(message)

logger = Logger()


def fail(message):
    logger.log(message)
    exit(1)

def run_command(command_tokens):
    completed_process = subprocess.run(command_tokens, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if completed_process.returncode != 0:
        command = " ".join(command_tokens)
        output = completed_process.stdout.decode('utf-8')
        fail(f"Failed to execute '{command}'. Output was:\n\n{output}\n")


def parse_version(version):
    try:
        str_tokens = version.split(".")

        if len(str_tokens) != 3:
            fail("Failed paring current version. There should be exactly 3 tokens.")

        int_tokens = [int(str_token) for str_token in str_tokens]
    except RuntimeError as error:
        fail("Failed parsing current version: " + str(error))

    return int_tokens


def version_tokens_to_str(int_tokens):
    return ".".join(str(int_token) for int_token in int_tokens)


def increment_version(current_version, part):
    current_version_tokens = parse_version(current_version)

    if part == "major":
        new_version_tokens = [current_version_tokens[0] + 1, 0, 0]
    elif part == "minor":
        new_version_tokens = [current_version_tokens[0], current_version_tokens[1] + 1, 0]
    elif part == "tiny":
        new_version_tokens = [current_version_tokens[0], current_version_tokens[1], current_version_tokens[2] + 1]
    else:
        fail("Part should be one of: major, minor or tiny.")

    return version_tokens_to_str(new_version_tokens)


def file_replace(file_replace_config, current_version, new_version):
    file_path = file_replace_config["path"]
    logger.log_verbose(f"Replacing version string in '{file_path}'.")

    search = file_replace_config["search_template"].format(version=current_version)
    replace = file_replace_config["search_template"].format(version=new_version)
    logger.log_verbose(f"Searching '{search}' and replacing for '{replace}'")

    if not os.access(file_path, os.R_OK | os.W_OK):
        fail(f"File '{file_path}' not found or not accessible")

    original_file_contents = None
    with open(file_replace_config["path"], "r") as file:
        original_file_contents = file.read()

    new_file_contents = original_file_contents.replace(search, replace)
    if original_file_contents == new_file_contents:
        fail(f"Nothing to replace in file '{file_path}'. Aborting since this looks like a misconfiguration or an"
              "inconsistent version in config file.")

    with open(file_replace_config["path"], "w") as file:
        file.write(new_file_contents)


def git_commit(modified_files, current_version, new_version):
    # TODO: make git path configurable
    commit_message = f"Bumping version: {current_version} → {new_version}"
    run_command(["git", "reset", "HEAD"])
    run_command(["git", "add"] + modified_files)
    run_command(["git", "commit", "-m", commit_message])


def git_tag(new_version):
    # TODO: make this format configurable
    tag = f"v{new_version}"
    run_command(["git", "tag", tag])


def main(**args):
    logger.set_verbose(args.get("verbose"))

    # Load config
    config_path = args.get("config_path") or ".bumpytrack.yml"
    try:
        config = yaml.load(open(config_path))
    except RuntimeError:
        fail("Failed to load config file at '{config_path}'.")

    # Get current version
    current_version = args.get("current_version") or config.get("current_version")
    if not current_version:
        fail("No way to obtain current version")
    logger.log(f"Current version: '{current_version}'")

    # Get new version
    if args.get("new_version"):
        new_version = args.get("new_version")
    elif args.get("part"):
        new_version = increment_version(current_version, args.get("part"))
    else:
        fail("No way to obtain a new version")
    logger.log(f"New version: '{new_version}'")

    # Replace version in config file and other configured files
    logger.log(f"Replacing version srting in files")
    file_replace_configs = [{"path": config_path, "search_template": "current_version: {version}"}]
    file_replace_configs += config.get("file_replaces", [])
    modified_files = []
    for file_replace_config in file_replace_configs:
        file_path = file_replace_config['path']
        file_replace(file_replace_config, current_version, new_version)
        modified_files.append(file_path)

    # Git commit file changes
    if args.get("git_commit") if args.get("git_commit") is not None else config.get("git_commit"):
        logger.log("Committing changes to GIT")
        git_commit(modified_files, current_version, new_version)

    # Git tag new version
    if args.get("git_tag") if args.get("git_tag") is not None else config.get("git_tag"):
        logger.log("Adding version tag to GIT")
        git_tag(new_version)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("part", help="Version token to bump: major, minor or tiny.")
    parser.add_argument("--current-version", help="Force current version instead using version in config file.")
    parser.add_argument("--new-version", help="Force new version instead using version in config file.")
    parser.add_argument("--git-commit", dest="git_commit", action="store_true", default=None, help="GIT: Commit files with version replacements.")
    parser.add_argument("--no-git-commit", dest="git_commit", action="store_false", default=None)
    parser.add_argument("--git-tag", dest="git_tag", action="store_true", default=None, help="GIT: Tag this reference with the new version.")
    parser.add_argument("--no-git-tag", dest="git_tag", action="store_false", default=None)
    parser.add_argument("--config-path", help="Path to config file. Defaults to .bumpytrack.yml in current directory.")
    parser.add_argument("--verbose", action="store_true")
    args_namespace = parser.parse_args()
    args = vars(args_namespace)

    main(**args)
