#!/usr/bin/env python
# *****************************************************************
# (C) Copyright IBM Corp. 2020, 2021. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# *****************************************************************

"""
*******************************************************************************
Script: create_version_branch.py
A script that can be used to create a version branch for an Open-CE feedstock.

The user will pass in a link to a repository, plus an optional commit. After
running the script, a new remote branch will be added to the repository with
a name based on the version number of the packages within the feedstock.
*******************************************************************************
"""

import os
import sys
import shutil
import pathlib
import git_utils

sys.path.append(os.path.join(pathlib.Path(__file__).parent.absolute(), '..'))
# pylint: disable=wrong-import-position
from open_ce import inputs
from open_ce import conda_utils
from open_ce import build_feedstock
from open_ce import utils

def _make_parser():
    ''' Parser input arguments '''
    parser = inputs.make_parser([git_utils.Argument.REPO_DIR, inputs.Argument.CONDA_BUILD_CONFIG],
                                    description = 'Create a version branch for a feedstock.')

    parser.add_argument(
        '--repository',
        type=str,
        required=False,
        help="""URL to the git repository.""")

    parser.add_argument(
        '--commit',
        type=str,
        required=False,
        help="""Commit to branch from. If none is provided, the head of the repo will be used.""")

    parser.add_argument(
        '--branch_if_changed',
        action='store_true',
        required=False,
        help="""If there was a change in version form the previous commit to the current one, create a version branch.""")

    return parser

def _get_repo_version(repo_path, variants, variant_config_files=None):
    '''
    Get the version of the first package that appears in the recipes list for the feedstock.
    '''
    saved_working_directory = os.getcwd()
    os.chdir(os.path.abspath(repo_path))
    for variant in variants:
        build_config_data, _ = build_feedstock.load_package_config(variants=variant, permit_undefined_jinja=True)
        if build_config_data["recipes"]:
            for recipe in build_config_data["recipes"]:
                rendered_recipe = conda_utils.render_yaml(recipe["path"],
                                                          variants=variant,
                                                          variant_config_files=variant_config_files,
                                                          permit_undefined_jinja=True)
                for meta, _, _ in rendered_recipe:
                    package_version = meta.meta['package']['version']
                    if package_version and package_version != "None":
                        os.chdir(saved_working_directory)
                        return package_version, meta.meta['package']['name']

    os.chdir(saved_working_directory)
    raise Exception("Error: Unable to determine current version of the feedstock")

def _get_repo_name(repo_url):
    if not repo_url.endswith(".git"):
        repo_url += ".git"
    return os.path.splitext(os.path.basename(repo_url))[0]

def _create_version_branch(arg_strings=None):# pylint: disable=too-many-branches
    parser = _make_parser()
    args = parser.parse_args(arg_strings)

    if args.repository:
        repo_name = _get_repo_name(args.repository)
        repo_url = args.repository
        repo_path = os.path.abspath(os.path.join(args.repo_dir, repo_name))
        print("--->Making clone location: " + repo_path)
        os.makedirs(repo_path, exist_ok=True)
        print("--->Cloning {}".format(repo_name))
        git_utils.clone_repo(repo_url, repo_path)
    elif args.repo_dir:
        repo_path = args.repo_dir
    else:
        repo_path = "./"

    if args.commit:
        git_utils.checkout(repo_path, args.commit)
    current_commit = git_utils.get_current_branch(repo_path)
    config_file = None
    if args.conda_build_configs:
        config_file = args.conda_build_configs
    try:
        git_utils.checkout(repo_path, "HEAD~")
        previous_version = _get_repo_version(repo_path, utils.ALL_VARIANTS(), config_file)

        git_utils.checkout(repo_path, current_commit)
        current_version = _get_repo_version(repo_path, utils.ALL_VARIANTS(), config_file)

        if args.branch_if_changed and current_version == previous_version:
            print("The version has not changed, no branch created.")
        else:
            if args.branch_if_changed:
                print("The version has changed, creating branch.")
                git_utils.checkout(repo_path, "HEAD~")
                branch_name = "r" + previous_version
            else:
                print("Creating branch.")
                branch_name = "r" + current_version

            if git_utils.branch_exists(repo_path, branch_name):
                print("The branch {} already exists.".format(branch_name))
            else:
                git_utils.create_branch(repo_path, branch_name)
                git_utils.push_branch(repo_path, branch_name)

            if args.branch_if_changed:
                git_utils.checkout(repo_path, current_commit)

        if args.repository:
            shutil.rmtree(repo_path)
    except Exception as exc:# pylint: disable=broad-except
        if args.branch_if_changed:
            git_utils.checkout(repo_path, current_commit)
        raise exc

if __name__ == '__main__':
    try:
        _create_version_branch()
    except Exception as exc:# pylint: disable=broad-except
        print("Error: ", exc)
        sys.exit(1)
