import lirc
import socket
import serial
import xml.etree.ElementTree as ET
import time


def get_lirc_client():
    client = lirc.Client(
        connection=lirc.LircdConnection(
            address=("192.168.1.97", 8765),
            socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            timeout=1
        )
    )
    return client


# get_confirm_code --> gets confirmation code of the specified command and returns it
# args:
#   if the command is a toggle one, like KEY_POWER for e.g, then toggle arg must be specified to
#   get the appropriate confirmation.
def get_confirm_code(command_name):
    tree = ET.parse('commands_confirmation.xml')
    root = tree.getroot()
    tv_name = root.find("chosen_tv")
    tv = root.find(tv_name.text)
    confirmation_codes = tv.find('confirmation_codes')
    for command in confirmation_codes.findall('command'):
        # print(command.get('name'), command.text)
        if command_name == command.get('name'):
            if command.get('toggle') == 'false':
                return command.text
            if command.get('toggle') == 'true':
                toggle_options = command.findall('toggle_option')

                if toggle_options is None or len(toggle_options) < 2:
                    raise Exception('command was set as toggle but no on and off option were found :' + command_name)
                else:
                    return toggle_options
            else:
                raise Exception('Configuration Format Error on command ' + command_name)

    raise Exception('Confirmation code not found in commands_confirmation.xml for command ' + command_name)


def config_schedule_parser():
    print()


# send_command --> sends IR command, repeats until usb serial confirmation
# returns bool:
#        true --> command send successfully and confirmation received
#        false -->confirmation was never found or another error occurred

def send_command(lirc_client, serial_socket, command="KEY_POWER", remote="Samsung_BN59-01175B", serial_tries=500,
                 ir_tries=5, toggle_option='', toggle_sleep=10, get_source=True):
    confirmation = ""
    j = 0
    usb_serial_skip_lines = get_skip_lines()
    confirm_code = get_confirm_code(command)
    toggle_wanted_confirmation = ''
    toggle_unwanted_confirmation = ''

    # if it is a toggle then i want to fill the toggle variables above
    if not isinstance(confirm_code, str):
        for toggle_opt in confirm_code:
            if toggle_opt.get('name') == toggle_option:
                toggle_wanted_confirmation = toggle_opt.text
            else:
                toggle_unwanted_confirmation = toggle_opt.text

    while j < ir_tries:
        try:
            j += 1
            serial_socket.flushInput()
            lirc_client.send_once(remote, command, repeat_count=1)
            i = 0
            # time.sleep(1)
            while i < serial_tries:
                try:
                    line_bytes = serial_socket.readline()
                    line_string = line_bytes.decode()

                    # if there is the possibility of having the tv kernel bursting the same message
                    # we want to ignore it
                    if is_skip_line(line_string, usb_serial_skip_lines):
                        continue

                    i += 1
                    # if it is not a toggle we just want to search for the confirmation code
                    if isinstance(confirm_code, str):
                        if confirm_code in line_string:
                            time.sleep(3)
                            return True
                        else:
                            print(line_string)
                    # but if it is a toggle we want to search for both confirmations but if we find the unwanted
                    # one then we need to repeat the command (works becuase its is a toggle)
                    else:
                        if toggle_wanted_confirmation in line_string:
                            print('TOGGLE WANTED = ' + line_string)
                            print(i)
                            time.sleep(toggle_sleep)
                            return True
                        # se encontrarmos outra vez
                        elif toggle_unwanted_confirmation in line_string:
                            print('TOGGLE UNWANTED = ' + line_string)
                            print(i)
                            time.sleep(toggle_sleep)
                            j -= 1
                            break

                except Exception as instance:
                    print(instance)

        except Exception as instance:
            print(instance)

    return False


# this function is needed in case that the tv kernel starts bursting printing errors or other messages.
# gets skip lines on xml configuration to avoid it
def get_skip_lines():
    try:
        tree = ET.parse('commands_confirmation.xml')
        root = tree.getroot()
        tv_name = root.find("chosen_tv")
        tv = root.find(tv_name.text)
        usb_serial_skip = tv.find("usb_serial_skip")
        return usb_serial_skip.findall('line')

    except Exception as instance:
        return ""


def is_skip_line(line, skip_lines):
    is_skip = False
    if not isinstance(skip_lines, str):
        for skip_line in skip_lines:
            if skip_line.text in line:
                is_skip = True

    return is_skip


def get_source_code(name):
    return


def test(lirc_client, serial_socket):
    # send_command(lirc_client, serial_socket, command="KEY_POWER", toggle_option='off')
    send_command(lirc_client, serial_socket, command="KEY_POWER", toggle_option='on')
    # send_command(lirc_client, serial_socket, command="KEY_LEFT")
    # send_command(lirc_client, serial_socket, command="")


def main():
    ser = serial.Serial('COM6', 115200)
    lirc_client = get_lirc_client()
    test(lirc_client, ser)
    ser.close()
    # c = get_confirm_code('KEY_POWER')


main()
