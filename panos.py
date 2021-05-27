from netmiko import ConnectHandler, ssh_exception
from libs import make_http_request, convert_xml_to_dict
import time, re, sys, os, logging, copy


SSH_MAX_RETRIES = 45
SSH_RETRY_SLEEP_TIME_SEC = 10

AUTOCOMMIT_MAX_RETRIES = 45
AUTOCOMMIT_RETRY_SLEEP_TIME_SEC = 5

def panos_connect_and_validate_ready(ip, **kwargs):
    def panos_command_successful(panos_connection):
        """
        Checks if the CLI is ready, responsive and responds to a command being sent to it.
        """
        print("Checking to see if PAN-OS is ready.")
        output = panos_connection.send_command('show system info')
        if "sw-version" in output:
            return True
        else: 
            return False

    def panos_autocom_complete(panos_connection):
        print("Checking if AutoCom is complete.")
        output = panos_connection.send_command('show jobs all').splitlines()
        for line in output:
            if "AutoCom" in line:
                AUTOCOMMIT_COMPLETE_KEYWORDS = ["FIN", "OK"]
                if all(keyword in line for keyword in AUTOCOMMIT_COMPLETE_KEYWORDS):
                    print('AutoCom is complete.')
                    return True
                else:
                    print('AutoCom has not yet completed.')
                    return False
        else:
            print('No AutoCom found in jobs, expecting that it has already completed.')
            return True

    def ssh_to_ngfw(**kwargs):
        """
        Initiates the connection and authenticates to the NGFW.
        """
        kwargs['device_type'] = 'paloalto_panos'
        if not 'username' in kwargs:
            kwargs['username'] = 'admin'

        if not 'password' in kwargs:
            kwargs['password'] = 'password'

        print(f'Connecting to {ip}...')
        try:
            connect = ConnectHandler(**kwargs)
            return connect
        except ssh_exception.NetmikoTimeoutException:
            logging.error('PAN-OS not ready: Connection timed out.')
            return False
        except ssh_exception.NetMikoAuthenticationException:
            logging.error('PAN-OS not ready: Authentication failed.')
            return False
        except ValueError:
            logging.error('PAN-OS not ready: Value Error.')
            return False

    connected = False
    retry_count = 0
    while retry_count < SSH_MAX_RETRIES:
        connected = ssh_to_ngfw(ip=ip, **kwargs)
        if connected:
            print('Connected and authenticated.')

            if panos_command_successful(panos_connection=connected):
                print('PAN-OS is ready.')

                autocommit_retry_count = 0
                autocommit_complete = False
                while autocommit_complete == False and autocommit_retry_count < AUTOCOMMIT_MAX_RETRIES:
                    if panos_autocom_complete(panos_connection=connected):
                        autocommit_complete = True
                        break
                    else: 
                        autocommit_retry_count += 1
                        print(f'Retrying... AutoCom retry count {autocommit_retry_count} / {AUTOCOMMIT_MAX_RETRIES}')
                        time.sleep(AUTOCOMMIT_RETRY_SLEEP_TIME_SEC)

                    if autocommit_retry_count == AUTOCOMMIT_MAX_RETRIES:
                        logging.error('AutCom did not complete within the retry parameters configured.')
                        sys.exit(1)
                return connected

        retry_count += 1
        print(f'Retrying... SSH retry count {retry_count} / {SSH_MAX_RETRIES}')
        time.sleep(SSH_RETRY_SLEEP_TIME_SEC)
    
    return False

def panos_enter_config_mode(panos_connection):
    if not panos_connection.check_config_mode():
        panos_connection.config_mode()

def check_if_panos_is_ready(ip, **kwargs):
    panos_connection = panos_connect_and_validate_ready(ip, **kwargs)
    if panos_connection:
        #panos_enter_config_mode(panos_connection)
        return panos_connection
    else:
        sys.exit(1)

def panos_commit(panos_connection):
    print('Committing changes.')
    panos_connection.commit()

def panos_configure_admin_acct(panos_connection, new_password):
    def panos_set_cmd_admin_acct_passwd(panos_connection, new_password):
        panos_connection.write_channel("set mgt-config users admin password\n")
        time.sleep(.5)
        panos_connection.read_channel()
        panos_connection.write_channel(f"{new_password}\n")
        time.sleep(.5)
        panos_connection.read_channel()
        panos_connection.write_channel(f"{new_password}\n")
        time.sleep(.5)
        panos_connection.read_channel()

    print('Setting the admin account with a new password.')
    panos_enter_config_mode(panos_connection)
    panos_set_cmd_admin_acct_passwd(panos_connection, new_password)
    panos_commit(panos_connection)
    panos_connection.exit_config_mode()

def panos_send_commands(panos_connection, command_type, commands):
    """
    Accepts a list of commands, or individual command as a string
    """
    print('Sending command: ', end='')
    def send_commands(panos_connection, commands):
        if isinstance(commands, list):
            for command in commands:
                print(command)
                print(panos_connection.send_command(command))
        elif isinstance(commands, str):
            print(command)
            print(panos_connection.send_command(commands))
    
    if command_type == 'operational':
        send_commands(panos_connection, commands)
    elif command_type == 'configure':
        panos_enter_config_mode(panos_connection)
        send_commands(panos_connection, commands)
        panos_commit(panos_connection)
        panos_connection.exit_config_mode()

def panos_create_apikey(username, password, host, **kwargs):
    print('Creating API key.')
    generate_api_key_url = f'/api/?type=keygen&user={username}&password={password}'

    # make http call with creds
    http_result_xml = make_http_request(host, generate_api_key_url, **kwargs)

    api_response = convert_xml_to_dict(http_result_xml)

    if api_response != None:
        if api_response['response']['@status'] == 'success':
            print('API key is: ', api_response['response']['result']['key'])
            return api_response['response']['result']['key']
        else:
            print('API Key generation was NOT successful. Error: ' + api_response['response']['result']['msg'])

def panos_create_vm_auth_key(host, panos_api_key, **kwargs):
    VM_AUTH_KEY_LIFETIME = 24 # in hours

    vm_auth_key_path = f"/api/?type=op&cmd=<request><bootstrap><vm-auth-key><generate><lifetime>{VM_AUTH_KEY_LIFETIME}</lifetime></generate></vm-auth-key></bootstrap></request>&key={panos_api_key}"
    http_result_xml = make_http_request(host, vm_auth_key_path, **kwargs)
    vm_auth_key = re.search(r"\d{4,}", http_result_xml.decode('utf-8')).group()
    return vm_auth_key

def create_bootstrap_terraform_files(number_of_students):
    required_files = ['gcp_bucket.template', 'init-cfg.template']
    files_that_exist = [file for file in required_files if os.path.isfile(file)]
    if required_files == files_that_exist:
        student_terraform_files = []
        with open('gcp_bucket.template', 'r', encoding = 'utf-8') as fout:
            content = fout.read()
        for student_number in range(number_of_students):  
            print(student_number)  
            student_terraform_files.append(content)
            student_terraform_files[student_number] = student_terraform_files[student_number].replace('firewallname', f'student-{student_number}')
    print(student_terraform_files)
