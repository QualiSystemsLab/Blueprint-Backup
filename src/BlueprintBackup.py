from quali_api_client import QualiAPIClient
import zipfile
import shutil
import os

from github import Github
import base64
import filecmp
from github import InputGitTreeElement
from collections import namedtuple

import json
from cloudshell.core.logger.qs_logger import get_qs_logger
from cloudshell.helpers.scripts import cloudshell_scripts_helpers as helpers
from cloudshell.workflow.orchestration.sandbox import Sandbox

class BluePrintBackupPackage:
    def __init__(self):
        self.cwd = os.getcwd()
        self.config_file = 'C:\ProgramData\QualiSystems\QBlueprintsBackup\config.json'
        self.configs = json.loads(open(self.config_file).read())
        self.sandbox = Sandbox()

        self.FileDescription = namedtuple('FileDescription', 'path contents executable')

        self.logger = get_qs_logger(log_file_prefix="CloudShell Sandbox Backup",
                           log_group=self.sandbox.id,
                           log_category='BluePrintBackup')


    # ////////////////////////////////////////////////////////////////////
    def are_dir_trees_equal(self,dir1, dir2):
        """
        Compare two directories recursively. Files in each directory are
        assumed to be equal if their names and contents are equal.

        @param dir1: First directory path
        @param dir2: Second directory path

        @return: True if the directory trees are the same and
            there were no errors while accessing the directories or files,
            False otherwise.
       """
        ignore_list = ["metadata.xml"]
        dirs_cmp = filecmp.dircmp(dir1, dir2,ignore=ignore_list)
        if len(dirs_cmp.left_only)>0 or len(dirs_cmp.right_only)>0 or \
            len(dirs_cmp.funny_files)>0:
            return False
        (_, mismatch, errors) =  filecmp.cmpfiles(
            dir1, dir2, dirs_cmp.common_files, shallow=False)
        if len(mismatch)>0 or len(errors)>0:
            return False
        for common_dir in dirs_cmp.common_dirs:
            new_dir1 = os.path.join(dir1, common_dir)
            new_dir2 = os.path.join(dir2, common_dir)
            if not self.are_dir_trees_equal(new_dir1, new_dir2):
                return False
        return True



    #////////////////////////////////////////////////////////////////////
    def file_description(self,path, contents, executable=False):
        """
        Build the file descriptor object

        @return: True if the directory trees are the same and
        there were no errors while accessing the directories or files,
        False otherwise.
        """
        return self.FileDescription(path, contents, executable)



    # ////////////////////////////////////////////////////////////////////
    def commit_package(self,file_descriptions,repo,is_new_blueprint):

        self.logger.info("Commit package")
        tree_els = [InputGitTreeElement(
            path=desc.path,
            mode='100644',
            type='blob',
            content=desc.contents
        ) for desc in file_descriptions]

        try:
            if is_new_blueprint:
                self.logger.info("Build Tree for first commit")
                master_ref = repo.get_git_ref('heads/master')
                master_sha = master_ref.object.sha
                base_tree = repo.get_git_tree(master_sha)

                tree = repo.create_git_tree(tree_els, base_tree)
                parent = repo.get_git_commit(master_sha)
                commit = repo.create_git_commit(self.commit_message, tree, [parent])
                master_ref.edit(commit.sha)

            self.logger.info("Update the prev commit")
            with open(self.fullZipfilePath, 'rb') as input_file:
                data = input_file.read()
            if self.fullZipfilePath.endswith('.zip'):
                old_file = repo.get_contents(self.zip_package_name)
                commit = repo.update_file('/' + self.zip_package_name, self.commit_message, data, old_file.sha)

            self.logger.info("Commit package completed")

        except Exception as e:
            self.logger.error("Error commiting blueprint {0}".format(str(e)))


    # ////////////////////////////////////////////////////////////////////
    def build_list_and_commit(self,repo,is_new_blueprint):

        self.logger.info("Build List of files")
        with open(self.fullZipfilePath, 'rb') as input_file:
            data = input_file.read()
       # if fullZipfilePath.endswith('.zip'):
       #     data = base64.b64encode(data)
        file_descriptions = [self.file_description(path=self.zip_package_name,
                                              contents="New BluePrint Package content")]
        self.commit_package(file_descriptions, repo,is_new_blueprint)



    # ////////////////////////////////////////////////////////////////////
    def ExportBlueprint_and_commit(self):
        """
            Export Blueprint on local machin and compare with old commit on Github
            before commiting and uploading the new exported package
        """

        self.logger.info("Start Exporting Blueprint")
        self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id, "Start Exporting blueprint")

        try:
            self.commit_comment = os.environ['comment']

        except Exception as e:
            self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,"Missing comment for commit")
            self.logger.info("Missing comment for commit")
            return

        self.commit_message = self.commit_comment + " commited by owner: " + self.sandbox.reservationContextDetails.owner_user

        ip = helpers.get_connectivity_context_details().server_address
        domain = helpers.get_reservation_context_details().domain

        contentlist = self.configs["GitPakageContentList"]
        temp_zip_path = self.configs['temp_zip_file']

        if not os.path.isdir(temp_zip_path):
            os.makedirs(temp_zip_path)

        self.zip_package_name = self.sandbox.reservationContextDetails.environment_name + '.zip'

        self.fullZipfilePath = temp_zip_path + '\\' + self.zip_package_name
        GitHub_Token = self.configs["GitHub Token"]
        #repo_url = self.configs["repo_url"]

        try:
            self.logger.info("Export the package")

            qac = QualiAPIClient(ip, '9000', self.sandbox.reservationContextDetails.owner_user
                                 ,self.sandbox.reservationContextDetails.owner_password, domain)

            qac.download_environment_zip(self.sandbox.reservationContextDetails.environment_name, self.fullZipfilePath)
            UnzipFolderName = temp_zip_path + '\\' + self.sandbox.reservationContextDetails.environment_name

            ## Unzip the pakage
            if not os.path.isdir(UnzipFolderName):
                os.makedirs(UnzipFolderName)

            self.logger.info("Unzip the package")
            zip = zipfile.ZipFile(self.fullZipfilePath)
            zip.extractall(UnzipFolderName)
            zip.close()

            ## Delete unrelevant files from package
            self.logger.info("Delete the unrelevant files from the package")
            for item in os.listdir(UnzipFolderName):
                if item not in contentlist:
                    path = UnzipFolderName + '\\' + item
                    shutil.rmtree(path)

            ## Zip the new package - overite the package
            self.logger.info("Zip the new blueprint package")
            os.chdir(os.path.dirname(UnzipFolderName))
            shutil.make_archive(UnzipFolderName, 'zip', UnzipFolderName)
            is_uploaded = False

            try:
                #First try to connect to regular Github url : https://github.com

                self.logger.info("Try to connect to the organization")
                git = Github(login_or_token=GitHub_Token)

                org = git.get_organization(self.configs["organization_name"])
                repo = org.get_repo(self.configs["Repository_name"])

            except Exception as e:
                #For enterprise github URL which is different than "https://github.com"
                try:
                    base_GitHubUrl  = self.configs["GitHub_Link"] + '/api/v3'
                    git = Github(login_or_token=GitHub_Token, base_url=base_GitHubUrl)
                    org = git.get_organization(self.configs["organization_name"])
                    repo = org.get_repo(self.configs["Repository_name"])
                except Exception as e:

                    self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                                         "Error getting git: {0}".format(str(e)))
                    self.logger.error("Error getting git {0}".format(str(e)))
                    raise e

            try:
                ##Download the previouse one
                self.logger.info("Try to download the prev commit of this blueprint")

                Prev_file_contents = repo.get_file_contents(self.zip_package_name)

                self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                                         "This is not the first commit for this blueprint")
                self.logger.info("This is not the first commit for this blueprint")

                prev_zip_path = temp_zip_path + '\\' + self.configs["Prev_Package_name"] + '.zip'
                fh = open(prev_zip_path, "wb")
                fh.write(Prev_file_contents.content.decode('base64'))
                fh.close()

                ## unzip the prev one
                self.logger.info("Unzip the prev blueprint package")
                prev_unzip = temp_zip_path + '\\' + self.configs["Prev_Package_name"]
                if not os.path.isdir(prev_unzip):
                    os.makedirs(prev_unzip)

                zip = zipfile.ZipFile(prev_zip_path)
                zip.extractall(prev_unzip)
                zip.close()

                if os.listdir(UnzipFolderName) and os.listdir(prev_unzip):
                    self.logger.info("Compering with prev commit for diff")
                    if self.are_dir_trees_equal(prev_unzip, UnzipFolderName):
                        self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                            "There is no diff from the prev commit")
                        self.logger.info("There is no diff from the prev commit - Not uploading the new commit!")

                    else:
                        self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                        "There is a diff from the prev commit")
                        self.logger.info("There is a diff from the prev commit")
                        self.build_list_and_commit(repo,is_new_blueprint=False)
                        is_uploaded = True

                self.logger.info("delete prev files")
                if os.path.isdir(prev_unzip):
                    shutil.rmtree(prev_unzip)
                if os.path.isfile(prev_zip_path):
                    os.remove(prev_zip_path)

            except Exception as e:
                self.logger.info("fail to download {0}".format(str(e)))
                if e.status == 404:
                    self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                        "This is the first commit for this blueprint")
                    self.logger.info("This is the first commit for this blueprint {0}".format(str(e)))

                    try:
                        if os.listdir(UnzipFolderName) and repo:
                            self.build_list_and_commit(repo,is_new_blueprint=True)
                            is_uploaded = True
                    except Exception as e:
                        self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                                                 "Error trying to build list and commit blueprint")
                        self.logger.error("Error trying to build list and commit blueprint {0}".format(str(e)))


            DownloadLink = self.configs['GitHub_Link'] + '/'+ self.configs["organization_name"] + '/' +\
                           self.configs["Repository_name"] + "/blob/master/"+ self.zip_package_name



            try:
                self.logger.info("Export and commit to Github completed")
                self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                                         "Export and commit to Github completed ")
                if is_uploaded:
                    self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,DownloadLink)

                self.logger.info("delete tmp files")

                shutil.rmtree(UnzipFolderName)
                if os.path.isfile(self.fullZipfilePath):
                    os.remove(self.fullZipfilePath)

            except Exception as e:
                self.logger.error("Error delete tmp files {0}".format(str(e)))

        except Exception as e:
            self.sandbox.automation_api.WriteMessageToReservationOutput(self.sandbox.id,
                                                     "Failed to export and commit {0}".format(str(e)))
            self.logger.error("Error - fail to extport and commit {0}".format(str(e)))
            raise e



