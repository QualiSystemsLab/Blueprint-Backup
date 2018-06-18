from BlueprintBackup import BluePrintBackupPackage
from cloudshell.helpers.scripts import cloudshell_scripts_helpers as helpers

import cloudshell.helpers.scripts.cloudshell_dev_helpers as dev_helpers

dev_helpers.attach_to_cloudshell_as('admin', 'admin', 'Global','b1db630b-195a-43eb-94c6-b8fff41872db',
                            server_address='localhost', cloudshell_api_port='8029',command_parameters={'comment':'New Blueprint by '})

def main():

    BluePrintBackupObj = BluePrintBackupPackage()
    BluePrintBackupObj.ExportBlueprint_and_commit()

if __name__ == '__main__':
    main()