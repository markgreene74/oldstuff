#!/usr/bin/python3

"""
Simple script to pull information about the failed disks and print a useful
template

For portability reason use subprocess instead of paramiko to connect to $server
in SSH and pull the RAID information

Giuseppe Cunsolo, January-May 2018
"""

# from X import Y
import socket
import argparse
import subprocess
import sys
import re
from datetime import datetime
from time import sleep
import curses

# some variables we are going to use through the script
# they are all here to make it easier to change them
template_closing = """
This is the template for closing, remember to change it.
Giuseppe Cunsolo
(555) 555 555"""

datacenter_info = {
    "A": ("Cluster A Location", "Cluster A Code",
          "Cluster A URL",
          "Cluster A Address",
          "Cluser A Contact details"),
    "B": ("Cluster B Location", "Cluster B Code",
          "Cluster B URL",
          "Cluster B Address",
          "Cluser B Contact details"),
    "C": ("Cluster C Location", "Cluster C Code",
          "Cluster C URL",
          "Cluster C Address",
          "Cluser C Contact details"),

}


class bcolors:
    """
    Simple way to print in colours without importing external modules
    print(bcolors.BOLD + "BOLD" + bcolors.ENDC)
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class server_object():
    """
    Contains all the server information (disks, location)
    parsed and easy to consume
    """

    def __init__(self, hwdisk, hinv, omreport):
        self.hwdisk = strip(hwdisk)
        self.hinv = strip(hinv)
        self.omreport = omreport
        self.stop_with_error = stop_with_error
        # init some object variables
        self.failed = False
        self.pred_failure = False
        self.not_in_use = False
        self.rebuilding = False
        self.print_templates = False
        # create a list of information we gather from the xymon hwdisk test
        # and init a empty dict which will contain all the data
        self.hwdisk_list = ["RAID type", "RAID status", "Test status"]
        self.hwdisk_data = {}
        # create a list of the server details and init a empty dict
        # which will contain all the data
        self.hinv_list = ["Location", "Rack", "RU", "Asset tag",
                          "Server model", "Warranty epoch"]
        self.server_details = {}
        # init lists
        # list of all disks
        self.list_all = []
        # list of failed disks
        self.list_failed = []
        # list of predictive failure disks
        self.list_predictive = []
        # list of disks not failed AND not in use in the RAID
        self.list_notinuse = []
        # list of disks rebuilding
        self.list_rebuilding = []
        # list of disks that need a replacement
        self.list_needreplacement = []
        #
        # kick in the parsing methods
        # self.omreport_p = self.parse_omreport_disks()
        self.parse_hwdisk()
        self.parse_hinv()
        if stop_with_error != "SSH":
            self.parse_omreport_disks()

    def parse_hwdisk(self):
        """
        Parse xymon hwdisk test and extract the result of the test
        """
        try:
            self.hwdisk_data['RAID type'] = re.findall(r'.*Virtual Disk.*(RAID-\d+).*', self.hwdisk, re.MULTILINE)[0]
            self.hwdisk_data['RAID status'] = re.findall(r'.*Virtual Disk.*is\s(\w+)\:?', self.hwdisk, re.MULTILINE)[0]
            self.hwdisk_data['Test status'] = re.findall(r'.*\|hw-disk\|(\w+)\|', self.hwdisk, re.MULTILINE)[0]
        except IndexError:
            print("Something is wrong with the data from Xymon test!")
            self.hwdisk_data['RAID type'] = ""
            self.hwdisk_data['RAID status'] = ""
            self.hwdisk_data['Test status'] = ""
        # TODO in the next version of the script these
        # should be tested singularly
        # TODO
        # if failed to ssh to the server build the list of failed disk based on
        # the xymon test
        # else:
        # just gather information about the test (RAID, RAID status etc)

    def parse_hinv(self):
        """
        Parse xymon hinv test and extract information about the server
        Location, Rack, RU, Asset tag, Server model, Warranty epoch
        """
        # Fix a bug where sometimes Xymon will put ",b '
        # in the middle of Rack location
        self.hinv = self.hinv.replace('", b\'', '')
        try:
            self.server_details['Location'] = re.findall(r'.*Rack location:\s+(.*),\s\w', self.hinv, re.MULTILINE)[0].split(", ")[0]
            self.server_details['Rack'] = re.findall(r'.*Rack location:\s+(.*),\s\w', self.hinv, re.MULTILINE)[0].split(", ")[1]
            # here we need to extract 1 or 2 RU, therefore the |
            # test for 2 RUs first, if that doesn't match extract 1 RU
            self.server_details['RU'] = re.findall(r'.*position:\s(\d*,\d*|\d*)', self.hinv, re.MULTILINE)[0]
            self.server_details['Asset tag'] = re.findall(r'.*Serial\s:\s(\w*)\s+\n', self.hinv, re.MULTILINE)[0]
            self.server_details['Server model'] = re.findall(r'.*HW type\s:\s(.*)\s+\n', self.hinv, re.MULTILINE)[0].strip()
        except IndexError:
            print("Something important is missing from the hinv!")
        # TODO in the next version of the script these values
        # should be tested singularly
        try:
            self.server_details['Warranty epoch'] = re.findall(r'.*HW\swarranty\s\(epoch\)\s\:\s(\d+).*', self.hinv, re.MULTILINE)[0]
        except IndexError:
            # Warranty epoch is empty in the hinv
            self.server_details['Warranty epoch'] = ""

    def parse_omreport_disks(self):
        """
        Parse omreport and extract information about disks
        """
        # result is a list which contains information about
        # each disk block organised in a tuple
        result = []
        # split omreport in single blocks for each disk
        blocks = []
        disk_string = ""
        for i in self.omreport:
            disk_string += str(i, 'utf-8')
        blocks = disk_string.split("\n\n")
        # for each block gather the information about the disks and
        # organize them in a tuple
        # build a list from these tuples
        for block in blocks:
            try:
                found0 = re.findall(r'^ID\s+\:\s(.*)\n', block,
                                    re.MULTILINE)
                found1 = re.findall(r'^Status\s+\:\s(.*)\n', block,
                                    re.MULTILINE)
                found2 = re.findall(r'^State\s+\:\s(\w+)\n', block,
                                    re.MULTILINE)
                found3 = re.findall(r'^Bus\sProtocol.*\:\s(\w+)\n', block,
                                    re.MULTILINE)
                found4 = re.findall(r'^Media.*\:\s(\w+)\n', block,
                                    re.MULTILINE)
                found5 = re.findall(r'^Failure\sPredicted.*\:\s(\w+)\n', block,
                                    re.MULTILINE)
                found6 = re.findall(r'^Progress.*\:\s(.*)\n', block,
                                    re.MULTILINE)
                found7 = re.findall(r'^Capacity.*\:\s(.*)\s\(.*\n', block,
                                    re.MULTILINE)
                found8 = re.findall(r'^Product\sID.*\:\s(\w+)\n', block,
                                    re.MULTILINE)
                found9 = re.findall(r'^Serial.*\:\s(\w+)\n', block,
                                    re.MULTILINE)
                #
                # found is a tuple of ten elements
                #  0 ID                              : 0:0:0
                #  1 Status                          : Ok
                #  2 State                           : Online
                #  3 Bus Protocol                    : SAS
                #  4 Media                           : HDD
                #  5 Failure Predicted               : No
                #  6 Progress                        : Not Applicable
                #  7 Capacity                        : 418.63 GB
                #  8 Product ID                      : ST3450857SS
                #  9 Serial No.                      : 3SK15JJK
                #
                # ('0:0:0', 'Ok', 'Online', 'SAS', 'HDD', 'No',
                #  'Not Applicable', '418.63 GB', 'ST3450857SS', '3SK15JJK')
                #
                found = (found0, found1, found2, found3, found4, found5,
                         found6, hr_disk_size(found7), found8, found9)
                # found7 is the only element of the tuple that is a string
                # and not a list; this is important when printing it
            except AttributeError:
                found = ''
            if found != '' and all(found):  # if found is not empty
                result.append(found)
        # now result is populated with the full list of disks
        # we will need this outside the function
        self.list_all = result
        # build the list of disks failed/in predictive failure/
        #                         rebuilding/not in the raid
        # and set the state variables accordingly
        for enclose in result:
            # check separately for failures and predictive failures
            # also checks for disks not failed AND not in the RAID (Ready)
            if enclose[2] == ["Ready"]:  # the disk is not in use
                self.not_in_use = True
                self.print_templates = True
                self.list_notinuse.append(enclose)
            elif enclose[2] == ["Rebuilding"]:  # the disk is rebuilding
                self.rebuilding = True
                self.print_templates = True
                self.list_rebuilding.append(enclose)
            elif enclose[2] != ["Online"]:  # the disk is failed/removed
                self.failed = True
                self.print_templates = True
                self.list_failed.append(enclose)
                # for now we are only going to add the disk
                # to the list self.list_needreplacement
                # if it's failed; this may change in the future if
                # we want to proactively replace disks in pred failure
                self.list_needreplacement.append(enclose)
            # add a disk to the predictive failure list
            # only if it's not failed
            if enclose[5] != ["No"] and enclose[2] == ["Online"]:
                self.pred_failure = True
                self.print_templates = True
                self.list_predictive.append(enclose)

    def print_progress(self):
        """
        This is a curses wrapper for the real function that
        print and refresh information about disk rebuilding
        """
        # stop if the server is offline
        if stop_with_error == "SSH":
            print(bcolors.FAIL + "The server may be offline!" +
                  bcolors.ENDC +
                  " Cannot get rebuilding information.\n")
            sys.exit(1)
        # we don't need to check if there are disks rebuilding
        # start the curses wrapper anyway;
        # when a disk starts rebuilding it will be picked up
        # and show in the curses screen
        #
        # we need to wrap the next part in curses
        # for a sane handling of screen refresh
        curses.wrapper(self.curses_progress)
        # Print a summary that will stay on screen
        # after the curses finished
        open_section("Disk(s) rebuilding")
        print("Rebuilding: %s" % len(self.list_rebuilding))
        for n in self.list_rebuilding:
            print("\n" + "ID:".ljust(20), n[0][0])
            print("Status:".ljust(20), n[1][0])
            print("State:".ljust(20), n[2][0])
            print("Serial No.:".ljust(20), n[9][0])
            print("Capacity:".ljust(20), n[7])
            print("Bus Protocol:".ljust(20), n[3][0])
            print("Progress:".ljust(20), n[6][0])
        close_section()

    def curses_progress(self, sc):
        """
        Print the progress of disk rebuilding; refresh every 60s
        Exit when 'q' is pressed
        """
        # change this for a different refresh rate
        # must be an even number (30, 60, 120)
        refresh_rate = 60
        dont_exit_the_loop = True
        #
        # if scrollok(False) and the list of disks rebuilding goes outside
        # the terminal size it fails with:
        # _curses.error: addwstr() returned ERR
        sc.scrollok(True)
        sc.nodelay(True)
        counter = 0
        sc.addstr("Disk(s) rebuilding:\n")
        # while True:
        while dont_exit_the_loop:
            sc.clear()
            counter += 1
            sc.addstr("Server: %s\t\tTime: %s\t\t(%s)\n" % (server,
                                                            str(datetime.now().strftime("%H:%M:%S")),
                                                            counter))
            sc.addstr("Rebuilding: %s\n" % len(self.list_rebuilding))
            for n in self.list_rebuilding:
            # for n in self.list_all:  # DEBUG print everything, replace self.list_rebuilding with self.list_all
                sc.addstr("\n" + "ID:".ljust(20) +
                          n[0][0] + "\n")
                sc.addstr("Status:".ljust(20) + n[1][0] + "\n")
                sc.addstr("State:".ljust(20) + n[2][0] + "\n")
                sc.addstr("Serial No.:".ljust(20) + n[9][0] + "\n")
                sc.addstr("Capacity:".ljust(20) + n[7] + "\n")
                sc.addstr("Progress:".ljust(20) + n[6][0] + "\n")
            sc.addstr("\nThe screen will refresh every %ss.\n" % str(refresh_rate))
            sc.addstr("Press 'q' to exit (wait until the application stops, may take a few seconds)")
            # sc.addstr("%s %s %s %s" % (0, 0, curses.LINES - 1, curses.COLS - 1))  # DEBUG
            sc.refresh()
            #
            # pull a new omreport, refresh self.omreport within the object
            # clear all the lists to avoid duplicates and
            # then trigger the parse method again
            #
            self.list_all = []
            self.list_failed = []
            self.list_predictive = []
            self.list_notinuse = []
            self.list_rebuilding = []
            self.list_needreplacement = []
            #
            self.omreport = pull_omreport(server)
            self.parse_omreport_disks()
            #
            # instead of waiting (sleep) for refresh_rate seconds and
            # check if the key 'q' is pressed, check every 1 second
            # for a total of time equal to refresh_rate seconds
            #
            for wait_for_it in range(0, refresh_rate, 1):
                try:
                    # check if the user pressed any key
                    key = sc.getkey()
                    # if key pressed is 'q' then exit
                    if key == "q":
                        dont_exit_the_loop = False
                        break
                except Exception:
                    # no input, stay in the while loop
                    pass
                sleep(1)

    def print_location(self):
        """
        Print the server location and warranty information
        """
        open_section("Server location")
        for i in self.hinv_list:
            print(i + ":".ljust(20 - len(i)), self.server_details[i])
        if self.server_details['Warranty epoch']:
            print("Warranty:".ljust(20), datetime.fromtimestamp(int(self.server_details['Warranty epoch'])))
        else:
            print("\nThe Warranty epoch is missing\n")
        print("\nURL:\n%s" % datacenter_info[letter][2])
        close_section()

    def print_serialn(self):
        """
        Print the full status, model, serial numbers for all the disks
        as requested by the user with the argument -s/--serial
        """
        if stop_with_error == "SSH":
            print(bcolors.FAIL + "The server may be offline!" +
                  bcolors.ENDC +
                  " The following information may not be accurate.\n")
        open_section("Disk information and serial numbers")
        for i in self.hwdisk_list:
            print(i + ":".ljust(20 - len(i)), self.hwdisk_data[i])
        for n in self.list_all:
            print("\n" + "ID:".ljust(20), n[0][0])
            print("Status:".ljust(20), n[1][0])
            print("State:".ljust(20), n[2][0])
            print("Bus Protocol:".ljust(20), n[3][0])
            print("Media:".ljust(20), n[4][0])
            print("Failure Predicted:".ljust(20), n[5][0])
            print("Progress:".ljust(20), n[6][0])
            print("Capacity:".ljust(20), n[7])
            print("Product ID:".ljust(20), n[8][0])
            print("Serial No.:".ljust(20), n[9][0])
        close_section()

    def print_compact(self):
        """
        Print a compact report as requested by the user with
        the argument -c/--compact
        """
        if stop_with_error == "SSH":
            print(bcolors.FAIL + "The server may be offline!" +
                  bcolors.ENDC +
                  " The following information may not be accurate.\n")
        open_section("Compact report")
        for i in ["Location", "Rack", "RU", "Asset tag", "Server model"]:
            print(i + ":".ljust(20 - len(i)), self.server_details[i])
        for i in self.hwdisk_list:
            print(i + ":".ljust(20 - len(i)), self.hwdisk_data[i])
        #
        print("Failed:".ljust(20), len(self.list_failed))
        print("Predictive failure:".ljust(20), len(self.list_predictive))
        print("Not in use:".ljust(20), len(self.list_notinuse))
        print("Rebuilding:".ljust(20), len(self.list_rebuilding))
        close_section()

    def print_result(self):
        """
        Print information about disks and template for replacement
        based on the arg flags (-t, etc)
        """
        if stop_with_error == "SSH":
            print(bcolors.FAIL + "The server may be offline!" +
                  bcolors.ENDC +
                  " The following information may not be accurate.\n")
        # Print the information from Xymon test
        open_section("Xymon test")
        for i in self.hwdisk_list:
            print(i + ":".ljust(20 - len(i)), self.hwdisk_data[i])
        close_section()

        open_section("Disk report")
        print("Failed:".ljust(20), len(self.list_failed))
        print("Predictive failure:".ljust(20), len(self.list_predictive))
        print("Not in use:".ljust(20), len(self.list_notinuse))
        print("Rebuilding:".ljust(20), len(self.list_rebuilding))
        # Print the list of disks that are rebuilding
        if self.rebuilding:
            print("Details of disks rebuilding:")
            for n in self.list_rebuilding:
                print("\n" + "ID:".ljust(20), n[0][0])
                print("Status:".ljust(20), n[1][0])
                print("State:".ljust(20), n[2][0])
                print("Serial No.:".ljust(20), n[9][0])
                print("Capacity:".ljust(20), n[7])
                print("Bus Protocol:".ljust(20), n[3][0])
                print("Progress:".ljust(20), n[6][0])
        close_section()

        # Print the templates if requested by the user or
        # if needed (= there are disks that need replacement)
        if self.print_templates or template_yes:
            # Print a template for JIRA ticket
            open_section("Template: JIRA Ticket")
            print("URL1?HOST=%s&SERVICE=disk\n" % server)
            print("URL2?HOST=%s&SERVICE=log\n" % server)
            print("{code:java}")
            print(self.hwdisk.replace("\n\n\n", ""))  # cut the 3x\n at the end
            print("{code}")
            # Print the server model, asset tag, warranty for the JIRA ticket
            print("-----\n{code:java}")
            print("Server model:".ljust(20), self.server_details['Server model'])
            print("Asset tag:".ljust(20), self.server_details['Asset tag'])
            if self.server_details['Warranty epoch']:
                print("Warranty:".ljust(20), datetime.fromtimestamp(int(self.server_details['Warranty epoch'])))
            else:
                print("Warranty:".ljust(20), "no information available")
            print("{code}")
            # Print the list of failed disks
            # when printing Capacity n[7] remember that is the only
            # item which is already a string
            if self.failed:
                print("-----\n{code:java}")
                print("Failed disk(s): %s" % len(self.list_failed))
                for n in self.list_failed:
                    print("\n" + "ID:".ljust(20), n[0][0])
                    print("Status:".ljust(20), n[1][0])
                    print("State:".ljust(20), n[2][0])
                    print("Serial No.:".ljust(20), n[9][0])
                    print("Capacity:".ljust(20), n[7])
                    print("Bus Protocol:".ljust(20), n[3][0])
                    print("Failure Predicted:".ljust(20), n[5][0])
                print("{code}")
            # Print the list of disks in predictive failure
            if self.pred_failure:
                print("-----\n{code:java}")
                print("Predictive failure disk(s): %s" % len(self.list_predictive))
                for n in self.list_predictive:
                    print("\n" + "ID:".ljust(20), n[0][0])
                    print("Status:".ljust(20), n[1][0])
                    print("State:".ljust(20), n[2][0])
                    print("Serial No.:".ljust(20), n[9][0])
                    print("Capacity:".ljust(20), n[7])
                    print("Bus Protocol:".ljust(20), n[3][0])
                    print("Failure Predicted:".ljust(20), n[5][0])
                print("{code}")
            # Print the list of disks not in the RAID
            if self.not_in_use:
                print("-----\n{code:java}")
                print("Disks not in use in the RAID: %s" % len(self.list_notinuse))
                for n in self.list_notinuse:
                    print("\n" + "ID:".ljust(20), n[0][0])
                    print("Status:".ljust(20), n[1][0])
                    print("State:".ljust(20), n[2][0])
                    print("Serial No.:".ljust(20), n[9][0])
                    print("Capacity:".ljust(20), n[7])
                    print("Bus Protocol:".ljust(20), n[3][0])
                    print("Failure Predicted:".ljust(20), n[5][0])
                print("{code}")
            close_section()

            # Print the email template for parcel delivery
            open_section("Template: Email to request a delivery")
            print(bcolors.FAIL +
                  "NOTE: Review this template before using it!\n" +
                  bcolors.ENDC + "\n\n")
            try:
                print(bcolors.BOLD + "Subject:" + bcolors.ENDC +
                      " %s HDD to Cluster %s %s\n" %
                      (self.list_all[0][7] + " " + self.list_all[0][3][0],
                       letter, datacenter_info[letter][0]))

                print(bcolors.BOLD + "Body:" + bcolors.ENDC + """
Please ship <N>x %s disks as per subject please.

=== <N>x %s disks to Cluster %s %s ===

= Address
%s
%s

= Contact details
%s
                                """ %
                      (self.list_all[0][7] + " " + self.list_all[0][3][0],
                       self.list_all[0][7] + " " + self.list_all[0][3][0],
                       letter, datacenter_info[letter][0],
                       self.server_details['Location'],
                       datacenter_info[letter][3],
                       datacenter_info[letter][4],))
            except IndexError:
                print(bcolors.FAIL + "The server may be offline!" +
                      bcolors.ENDC +
                      " Unable to print this section.\n")
            print(template_closing)
            close_section()

            # Print the smart hands template
            open_section("Template: Smart hands ticket")
            print(bcolors.FAIL +
                  "NOTE: Review this template before using it!\n" +
                  bcolors.ENDC + "\n\n")
            if self.list_needreplacement and stop_with_error != "SSH":
                # if the list is not empty AND we can connect to the server
                # (= the disk info is populated) print the SH template
                # with the real information, print a template for each disk
                for i in self.list_needreplacement:
                    self.print_sh_template(False, i)
            elif stop_with_error == "SSH":
                sys.exit("The server is offline!")
                # TODO
                # if cannot connect to the server print an empty template
            else:
                # else, print the mock information
                self.print_sh_template()
            print(template_closing)
            close_section()

    def print_sh_template(self, mock=True, disk=()):
        """
        Print the disk replacement template;
        too complicated to add inline in the print_result method
        """
        # we are going to work with some variables local to the method
        # replace_size      disk size
        # replace_type      disk type
        # replace_enclose   disk enclose
        # replace_sn        disk sn
        #
        # replace_vars = (replace_size + " " + replace_type,
        #                 replace_enclose,
        #                 replace_sn
        #              )
        #
        if mock:
            # pick the mock information from the first disk
            replace_vars = (self.list_all[0][7] + " " +
                            self.list_all[0][3][0],
                            self.list_all[0][0][0][-1:],
                            self.list_all[0][9][0],
                            )
            print(bcolors.FAIL +
                  "This is the mock template - DO NOT USE THIS TEMPLATE FOR A REAL REPLACEMENT\n" +
                  bcolors.ENDC)
        else:
            print("- Printing the template for disk: %s -\n" % disk[0][0])
            replace_vars = (disk[7] + " " +
                            disk[3][0],
                            disk[0][0][-1:],
                            disk[9][0],
                            )
        print("Hello %s,\n" % self.server_details['Location'])
        print("This is a remote hands request for replacing one HDD. Thanks for following these steps:\n")
        print("1. take one disk of size %s from <...>" % replace_vars[0])
        print("2. locate the server > %s < and replace disk in bay %s (Serial number: %s)" %
              (server, replace_vars[1], replace_vars[2]))
        print("""
    Server:    %s
    Rack:      %s
    RU:        %s
    Asset Tag: %s
    Model:     %s

3. label the broken disk as "FAILED" """ %
              (server,
               self.server_details['Rack'],
               self.server_details['RU'],
               self.server_details['Asset tag'],
               self.server_details['Server model']))


def arguments():
    """
    Parse arguments and return help message if the script is invoked with -h
    there is one (mandatory) arg, which is the server we want to check
    """
    # version = "0.1 - January 2018"
    # version = "0.2 - April 2018"
    # version = "0.3 - May 2018"
    version = "0.3.1 - May 2018"  # Fixed duplicate entries when using -p
    prg_description = 'Pull the information about failed disk(s) and print templates to raise a JIRA ticket, Smart Hands requests, etc.'
    # #
    parser = argparse.ArgumentParser(description=prg_description,
                                     prog='failed_disk script')
    parser.add_argument('server', help='The server hostname, ex: prx11a')
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s version ' + version)
    parser.add_argument('-c', '--compact', help='print a compact report',
                        action='store_true')
    parser.add_argument('-s', '--serial', help='print the status, model, serial number for all the disks',
                        action='store_true')
    parser.add_argument('-p', '--progress', help='print the progress of disks rebuilding; press \'q\' to exit',
                        action='store_true')
    parser.add_argument('-t', '--template', help='print the templates even if there is no disk failed or in predictive failure',
                        action='store_true')
    args = parser.parse_args()
    """
    perform sanity check on arguments
    """
    # check that server is a string of 3 characters followed by 2 numbers
    if not re.match('[a-z][a-z][a-z][0-9][0-9][a-z]+', args.server):
        sys.exit("ERROR: Server not valid\n")
    # check for incompatible options: only 1 option can be selected
    # between -c/-s/-p/-t
    if sum([args.template, args.serial, args.progress, args.compact]) > 1:
        sys.exit("ERROR: You have selected incompatible options\n")
    return args.server, args.template, args.serial, args.progress, args.compact


def query_xymon(host, test):
    """
    Query Xymon for $host.$test
    returns a string
    """
    # initialise variable data, we can do this in two different ways
    # data = '' # data is a string
    data = []   # data is a list
    xserver = "abcd"
    parameter = "xymondlog " + host + "." + test
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.settimeout(10)
    sock.connect((xserver, 11984))
    sock.send(parameter.encode('ascii', 'xmlcharrefreplace'))
    sock.shutdown(socket.SHUT_WR)
    """
    Loop to fetch data from Xymon
    """
    while True:
        # counter = 0
        chunk = sock.recv(4096)
        if not chunk:
            break
        # data += str(chunk)         # data is a string
        data += [chunk]              # data is a list
    """
    End of the loop
    """
    sock.close()
    # return data                # data is a string
    return str(data)             # data is a list


def pull_omreport(server):
    """
    User subprocess to connect to $server and run the command
    "omreport storage pdisk controller=0" with sudo
    """
    # use the global variable stop_with_error
    global stop_with_error
    #
    command = "sudo omreport storage pdisk controller=0"
    ssh = subprocess.Popen(["ssh", "%s" % server, command],
                           shell=False,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:  # print the error and exit gracefully
        error = ssh.stderr.readlines()
        sys.stderr.write("ERROR: %s\n" % strip(str(error)))
        stop_with_error = "SSH"
        # if cannot ssh to the server do NOT exit
        # print the error, assign the variable stop_with_error and
        # continue the execution
        #
        # Uncomment this if you want the script to exit
        # when there is an error connecting in ssh
        # sys.exit(1)
    else:
        # do not process the result, just return the raw data
        return result


def strip(string):
    """
    Strip a string of all the extra characters, HTML tags for a cleaner output
    """
    """
    Strip
    <B></B>, <H3></H3>, <PRE></PRE>, <FONT color=></FONT>

    strips [b' and '] at the beginning/end, respectively, of the
    Xymon output

    strips ', b' from the output of omreport

    replaces
    \\n with \n so that a newline is printed
    \\t with \t so that a tab is printed

    also replaces &green/red/yellow/clear/blu with green/red/yellow/clear/blu
    """
    # strips [b' and ']
    string = string.replace("[b'", "").replace("']", "")  # use "" to contain '
    string = string.replace('[b"', '').replace('"]', '')  # use "" to contain '
    # replace \\n
    string = string.replace('\\n', '\n')
    # replaces \\t
    string = string.replace('\\t', '\t')
    # replaces \\r
    string = string.replace('\\r', '\r')
    # replaces &color
    colours = ['green', 'red', 'yellow', 'blu', 'clear']
    for i in colours:
        string = string.replace('&' + i, i)
    # strips html tags
    string = string.replace('<B>', '').replace('</B>', '')
    string = string.replace('<H3>', '').replace('</H3>', '')
    string = string.replace('<PRE>', '').replace('</PRE>', '')
    string = string.replace('<FONT color=grey>', '')
    string = string.replace('<FONT color=yellow>', '').replace('</FONT>', '')
    # strips ', b'
    string = string.replace("', b'", "")
    return string


def get_cluster_info(server):
    """
    get the cluster letter and based on that assign variables like
    datacenter address, link to racktables etc
    """
    #
    cluster_letter = re.search("[a-z][a-z][a-z][0-9][0-9](.*)", server).group(1).upper()
    # check if it's a valid cluster
    if cluster_letter not in datacenter_info:
        sys.exit("ERROR: I don't have cluster %s in my list.\n" % cluster_letter)
    print("Cluster " + bcolors.BOLD + cluster_letter +
          " " + datacenter_info[cluster_letter][0] +
          " " + datacenter_info[cluster_letter][1] +
          " " + bcolors.ENDC + "\n")
    return cluster_letter


def hr_disk_size(alist):
    """
    Convert the disk size to human readable format, for example:
    "558.38 GB" to "600 GB"
    """
    # This dictionary contains the conversion
    disksize_info = {
        "418.63 GB": "450 GB",
        "558.38 GB": "600 GB",
        "931.00 GB": "1 TB",
        "1,862.50 GB": "2 TB",
        "2,794.00 GB": "3 TB",
        "3,725.50 GB": "4 TB",
    }
    # we need to do a bit of error check as alist could be empty
    astring = ""            # astring is empty
    if alist:               # the list is not empty
        astring = alist[0]  # extract the string from the list
    # check if astring is contained in the dict
    if astring in disksize_info:
        return disksize_info[astring]
    else:
        return ""


def open_section(string):
    string = " " + string + " "
    print(bcolors.BOLD + string.center(80, "=") +
          bcolors.ENDC)


def close_section():
    print(bcolors.BOLD + "-" * 80 +
          bcolors.ENDC + "\n\n")


if __name__ == "__main__":
    # execute only if run as a script
    # set this variable if we need to stop the execution
    stop_with_error = ""
    # check the args and assign the variable server that contains $server
    server, template_yes, serial_yes, progress_yes, compact_yes = arguments()
    # get the cluster information for server and
    # print a header with some initial information
    print("Gathering disks information for " + bcolors.BOLD + server +
          bcolors.ENDC + "\n")
    letter = get_cluster_info(server)
    # query Xymon for $server.hw-disk and store the raw result in result_hwdisk
    result_hwdisk = query_xymon(server, "hw-disk")
    # query Xymon for $server.hinv and store the raw result in result_hinv
    result_hinv = query_xymon(server, "hinv")
    # connect to server, see the comment above about not using paramiko
    # pull the result of omreport storage pdisk controller=0
    omreport = pull_omreport(server)
    this_server = server_object(result_hwdisk, result_hinv, omreport)
    # if option(s) -p/-c have been selected
    # call the appropriate function and then exit
    if progress_yes:
        this_server.print_progress()
        sys.exit()  # exit with 0
    elif compact_yes:
        this_server.print_compact()
        sys.exit()  # exit with 0
    # if not, continue with the normal logic
    # print the server location
    this_server.print_location()
    # decide if we are going to just print the serial numbers
    # or the full result
    if serial_yes:
        this_server.print_serialn()
    else:
        this_server.print_result()
    # That's all folks!
