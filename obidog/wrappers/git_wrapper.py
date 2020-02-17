import os
import tempfile

import git

from obidog.config import PATH_TO_OBENGINE
from obidog.exceptions import InvalidObEngineGitRepositoryException
from obidog.logger import log

OBENGINE_GIT_URL = os.environ.get(
    "OBENGINE_GIT_URL",
    "https://github.com/Sygmei/ObEngine")
OBENGINE_GIT_SSH = os.environ.get(
    "OBENGINE_GIT_SSH",
    "git@github.com:Sygmei/ObEngine"
)

def check_git_directory():
    global PATH_TO_OBENGINE
    if PATH_TO_OBENGINE is not None:
        log.debug(f"Found existing ÖbEngine repository in {PATH_TO_OBENGINE}")
    else:
        log.debug("Cloning ÖbEngine repository...")
        PATH_TO_OBENGINE = clone_obengine_repo()
        os.environ["OBENGINE_GIT_DIRECTORY"] = PATH_TO_OBENGINE
    log.debug("Checking ÖbEngine repository validity...")
    if not check_obengine_repo(PATH_TO_OBENGINE):
        raise InvalidObEngineGitRepositoryException(PATH_TO_OBENGINE)
    log.info(f"Using ÖbEngine repository in {PATH_TO_OBENGINE}")
    return PATH_TO_OBENGINE

def clone_obengine_repo():
    path = tempfile.mkdtemp()
    git.Repo.clone_from(
        OBENGINE_GIT_URL,
        path,
        branch='master'
    )
    return path


def check_obengine_repo(git_dir):
    try:
        repo = git.Repo(git_dir)
    except:
        return False
    return (
        OBENGINE_GIT_URL in repo.remote().urls,
        OBENGINE_GIT_SSH in repo.remote().urls
    )