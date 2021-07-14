
import logging, argparse, sys, json, os
from panos import check_if_panos_is_ready, panos_configure_admin_acct, panos_send_commands, panos_create_apikey, panos_create_vm_auth_key, create_bootstrap_terraform_files
from libs import make_http_request, convert_xml_to_dict, write_to_file, read_from_file

TMP_FILE = 'tracker.tmp'

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.WARN)

parser = argparse.ArgumentParser()
parser.add_argument("--ip", help="IP address of PAN-OS device")
parser.add_argument("--login-username", help="Username to log in with")
parser.add_argument("--login-password", help="Password to use")
parser.add_argument("--priv-ssh-key", help="Path to ssh private key file")
parser.add_argument("--change-password-to", help="Path to ssh private key file")
parser.add_argument("--create-bootstrap", help="Creates bootstrap folder structure and necessary files for students")
parser.add_argument("--panorama-serial-number", help="Serial number for Panorama registration")
parser.add_argument("--create-api-key", help="Creates API key for PAN-OS device", action="store_true")

args = parser.parse_args()

def main():

    panos_connection = None

    if args.ip:
        ip = args.ip

    if args.priv_ssh_key:
        use_keys = True
        key_file = args.priv_ssh_key
    else:
        use_keys = False
        key_file = ''

    if args.login_username:
        username = args.login_username
    else:
        username = 'admin'

    if args.login_password:
        password = args.login_password
    else:
        password = 'admin'

    if args.change_password_to:
        new_password = args.change_password_to

    if 'ip' in locals() and 'username' in locals():
        panos_connection = check_if_panos_is_ready(ip=ip, username=username, password=password, use_keys=use_keys, key_file=key_file)

    if 'new_password' in locals():
        panos_configure_admin_acct(panos_connection, new_password=new_password)
        password = new_password # password has been changed, so use the new_password moving forward.
        
    if 'ip' in locals():
        panos_send_commands(panos_connection, command_type='operational', commands=['show clock'])

    if args.create_api_key:
        panos_api_key = panos_create_apikey(username, password, ip)

    #if args.create_api_key and args.create_bootstrap:
    if args.create_bootstrap and 'ip' in locals():
        student_state = {
            'number_of_students_entered': 0,
            'student_number_processed': 0
        }

        if read_from_file(TMP_FILE):
            #number_of_students_remaining = int(read_from_file(TMP_FILE))
            student_state_filedata = json.loads(read_from_file(TMP_FILE))
            print('student_state_data ', student_state_filedata) ###
            student_state['number_of_students_entered'] = student_state_filedata['number_of_students_entered'] ###
            student_state['student_number_processed'] = student_state_filedata['student_number_processed'] ###

            #student_number = number_of_students_remaining
            print(f"Current student number: {student_state['student_number_processed']}")
            #print(write_to_file(TMP_FILE, f'{number_of_students_remaining - 1}'))

        else:
            number_of_students = int(args.create_bootstrap)
            print(f'No config found: number of students entered: {number_of_students}')

            student_state['number_of_students_entered'] = number_of_students - 1 # counting from 0 ###

            #print(write_to_file(TMP_FILE, f'{number_of_students - 1}'))
            print(write_to_file(TMP_FILE, json.dumps(student_state))) ###

            #student_number = number_of_students
            print(f"Current student number being processed: {student_state['student_number_processed']}") ###

        #number_of_students_remaining = student_number - 1
        #print(f'number_of_students_remaining: {number_of_students_remaining}')

        panos_send_commands(panos_connection, command_type='configure', commands=[
            'set deviceconfig system timezone US/Pacific',
            f"set deviceconfig system hostname Panorama-student-{student_state['student_number_processed']}",
            'set deviceconfig system dns-setting servers primary 1.0.0.1',
            'set deviceconfig system ntp-servers primary-ntp-server ntp-server-address pool.ntp.org',
            'set template sdwan-template config vsys vsys1',
            'set template sdwan-template config deviceconfig system',
            'set device-group sdwan devices',
            'set device-group sdwan reference-templates sdwan-template'])
        
        #try:
        #    if read_from_file(TMP_FILE):
        #        number_of_students_remaining = int(read_from_file(TMP_FILE))
        #        student_number = number_of_students_remaining
        #        print(write_to_file(TMP_FILE, f'{number_of_students_remaining - 1}'))
#
        #    else:
        #        number_of_students = int(args.create_bootstrap)
        #        print(f'No config found: number of students entered: {number_of_students}')
        #        print(write_to_file(TMP_FILE, f'{number_of_students}'))
        #        student_number = number_of_students
        #    number_of_students_remaining = number_of_students - 1
        #    print(f'number_of_students_remaining: {number_of_students_remaining}')
        #except:
        #    sys.exit('ERROR: Bootstrap parameter entered was not a number. Please enter number of students to build the bootstrap for.')
        vm_auth_key = panos_create_vm_auth_key(ip, panos_api_key)
        #if number_of_students_remaining < 1:
        if student_state['student_number_processed'] > student_state['number_of_students_entered']:
            print("student_state['student_number_processed'] > student_state['number_of_students_entered'], removing temp file")
            #print('number_of_students_remaining < 1, removing file')
            os.remove(TMP_FILE)
        #create_bootstrap_terraform_files(student_number, vm_auth_key)
        create_bootstrap_terraform_files(student_state['student_number_processed'], vm_auth_key)

        student_state['student_number_processed'] += 1 ###
        print(write_to_file(TMP_FILE, json.dumps(student_state))) ###

    if args.panorama_serial_number:
        panos_send_commands(panos_connection, command_type='operational', commands=[f'set serial-number {args.panorama_serial_number}', 'request license fetch'])

    if panos_connection:
        panos_connection.disconnect()

main()