
import logging, argparse, sys
from panos import check_if_panos_is_ready, panos_configure_admin_acct, panos_send_commands, panos_create_apikey, panos_create_vm_auth_key, create_bootstrap_terraform_files
from libs import make_http_request, convert_xml_to_dict

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.WARN)

parser = argparse.ArgumentParser()
parser.add_argument("--ip", help="IP address of PAN-OS device")
parser.add_argument("--login-username", help="Username to log in with")
parser.add_argument("--login-password", help="Password to use")
parser.add_argument("--priv-ssh-key", help="Path to ssh private key file")
parser.add_argument("--change-password-to", help="Path to ssh private key file")
parser.add_argument("--create-bootstrap", help="Creates bootstrap folder structure and necessary files for students")
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
    if args.create_bootstrap:
        try:
            number_of_students = int(args.create_bootstrap)
        except:
            sys.exit('ERROR: Bootstrap parameter entered was not a number. Please enter number of students to build the bootstrap for.')
        #vm_auth_key = panos_create_vm_auth_key(ip, panos_api_key)
        #print(vm_auth_key)
        create_bootstrap_terraform_files(number_of_students)

    if panos_connection:
        panos_connection.disconnect()

main()