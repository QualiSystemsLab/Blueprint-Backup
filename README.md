 Blueprint Backup
Script to Export blueprint and Upload it to GitHub

 Blueprint Backup
The purpose of this utility is run an orchestration command  that export the bluepriont package to local location on the execution server
compare the package with the last commit, if there is a difference it will upload the edited package to the given repository
this is a python script using config file

You'll need to create github repository with readme file and generate a token key
This repository will be used to upload blueprint package that was exported from cloudshell
the package name will be the blueprint name zip file


the config file contains the following:
 GitHub Token - Github token key of your repository on github
 GitPakageContentList - The files and folders we want to include in the package we upload to the github repository, the rest will be removed
 temp_zip_file - location to export the blueprint pachage on your local machine 
 Prev_Package_name - local package name for last package that was uploaded to the github for this blueprint name
 organization_name - organization name in Github
 Repository_name - the repository name in Github 
 GitHub_Link - https base url of your github for example: https://git.xxxx.com

The config file must reside in the following location on each execution server 
C:\ProgramData\QualiSystems\QBlueprintsBackup and must be named 'config.json'


