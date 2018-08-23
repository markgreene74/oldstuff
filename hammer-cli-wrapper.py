#!/usr/bin/env python
"""
Provide a wrapper for creating/printing info/deleting nodes
"""

import argparse
import subprocess
import sys
import time
import re


def arguments():
    """
    Parse arguments and return help message
    """
    helper_version = "0.2"
    helper_descr = "Wrapper for hammer-cli/Foreman nodes action"
    parser = argparse.ArgumentParser(description=helper_descr)
    parser.add_argument("-v", "--version", action="version", version=helper_version)
    parser.add_argument(
        "--create",
        nargs=5,
        help="create a new node, requires in this order: hostname IP vCPU memory disk",
    )
    # NOTE: hostname NOT fqdn; memory and disk are expressed in GB
    # Example: --create testvm 192.168.1.200 1 2 10
    parser.add_argument("--delete", nargs=1, help="delete a node, requires node FQDN")
    parser.add_argument(
        "--info", nargs=1, help="print information about a node, requires node FQDN"
    )
    parser.add_argument(
        "--list", action="store_true", help="print information about all the nodes"
    )
    parser.add_argument(
        "--rebuild", nargs=1, help="trigger rebuilding of a node, requires node FQDN"
    )
    args = parser.parse_args()
    # args is a namespace
    # Namespace(create=None, delete=None, info=None, list=False, rebuild=None)
    return args.create, args.delete, args.info, args.list, args.rebuild
    # print(args)  # DEBUG


def remote_reboot(server):
    """
    Use subprocess to connect to $server and reboot it
    """
    #
    print("Rebooting %s" % server)
    command = 'shutdown -r +1 "Reboot to rebuild the node"'
    ssh = subprocess.Popen(
        ["ssh", "%s" % server, command],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    result = ssh.stdout.readlines()  # it's a list
    error = ssh.stderr.readlines()  # it's a list
    hr_result = " ".join(map(str, result))
    hr_error = " ".join(map(str, error))

    #
    # NOTE: SSH print some information (such as "The system is going
    # down for reboot at") to stderr;
    # we need to catch the exit code to assess if there is an error
    while ssh.poll() is None:
        # subprocess has not exited yet, wait
        time.sleep(0.5)
    # now it's time to get the return code
    # print("SSH return code: %s" % ssh.returncode)  # DEBUG
    if ssh.returncode > 0:  # print the error and exit gracefully
        sys.stderr.write("ERROR: %s\n" % str(hr_error))
        # if cannot ssh to the server do NOT exit
        # print the error
        #
        # Uncomment this if you want the script to exit
        # when there is an error connecting in ssh
        # sys.exit(1)
    else:
        # print SSH output
        # print("SSH output:\n%s" % hr_result)  # DEBUG
        # print(hr_error)  # DEBUG
        return hr_result + hr_error


def run_hammer(hmmr_args, shallweprint=True):
    """
    Use subprocess to nicely wrap the hammer-cli command
    """
    # print("type:" % type(hmmr_args))  # DEBUG
    # print("args:" % hmmr_args)  # DEBUG
    hammer = subprocess.Popen(
        ["hammer %s" % hmmr_args],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = hammer.stdout.readlines()  # it's a list
    error = hammer.stderr.readlines()  # it's a list
    hr_result = " ".join(map(str, result))
    hr_error = " ".join(map(str, error))
    if shallweprint:
        print("hammer-cli output: \n%s" % hr_result)
    if error:
        sys.stderr.write("hammer-cli error: %s\n" % hr_error)
        sys.exit(1)
    return hr_result


def run_command(run_args, shallweprint=True):
    """
    Use subprocess to nicely wrap a shell command
    """
    r_command = subprocess.Popen(
        [run_args], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    result = r_command.stdout.readlines()  # it's a list
    error = r_command.stderr.readlines()  # it's a list
    hr_result = " ".join(map(str, result))
    hr_error = " ".join(map(str, error))
    if shallweprint:
        print("CMD output: \n%s" % hr_result)
    while r_command.poll() is None:
        # subprocess has not exited yet, wait
        time.sleep(0.5)
    if error or r_command.returncode:
        # sys.stderr.write("Exit code: %s\n" % r_command.returncode)  # DEBUG
        sys.stderr.write("CMD error: %s\n" % hr_error)
        sys.exit(1)
    return hr_result


def func_create(node_create, IP_create, vCPU_create, memory_create, disk_create):
    # hammer host create --help
    #
    # create needs 5 args: hostname, IP, vCPU, memory (GB), disk (GB)
    # example:
    # --create testvm 192.168.1.200 1 2 10
    # hammer host create (...) --name=testvm.test.mydomain.com
    #
    # check memory, if < 2 GB we cannot build the machine
    if int(memory_create) < 2:
        print(
            "ERROR: at least 2 GB RAM is needed to create the node\nStopping execution"
        )
        sys.exit(1)
    #
    # gather information from the build server:
    # we need the FQDN and the domain, example:
    # [foreman.[test.mydomain.com]]
    foreman_fqdn = run_command("hostname -f", False).strip()
    foreman_domain = run_command("hostname -d", False).strip()
    # assign args to variables
    IP = IP_create
    vCPU = vCPU_create
    memory = str(int(memory_create) * 1073741824)
    disk = disk_create
    # NOTE: memory has to be a string representing the number in bytes
    # for example: 2 GB correspond to 2147483648
    # 2 * 1024 * 1024 * 1024
    #
    # before proceeding we need to check the IP address
    output = run_hammer("host list", False)
    if IP in output:
        regexIP = IP.replace(".", "\.")
        # in Python 3 this will work
        # matchedline = re.search(r'^(.*)' + regexIP,
        #                         output, re.MULTILINE)[0]
        # but in Python 2 we need to use group(0) instead
        matchedline = re.search(r"^(.*)" + regexIP, output, re.MULTILINE).group(0)
        ID = matchedline.split()[0]
        node = matchedline.split()[2]
        print(
            "%s is already used by an existing node: %s (ID %s)\nStopping execution"
            % (IP, node, ID)
        )
        sys.exit(1)
    # and the hostname
    if node_create in output:
        print(
            "%s is already used by an existing node\nStopping execution" % node_create
        )
        sys.exit(1)
    #
    # as we need to replace multiple variables we will use string concat
    # here, also it should help with cleanliness
    create_str = (
        '--environment="production" --puppet-proxy="'
        + foreman_fqdn
        + '" --puppet-ca-proxy="'
        + foreman_fqdn
        + "\" --compute-resource=ovirt --compute-attributes=\"cluster='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',cores="
        + vCPU
        + ",memory="
        + memory
        + ",start=1\" --interface=\"primary=true,managed=true,provision=true,type=interface,compute_network='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',ip="
        + IP
        + ',subnet_id=1,domain_id=1" --volume="size_gb='
        + disk
        + ",storage_domain='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',bootable=1\" --domain=\""
        + foreman_domain
        + '" --architecture="x86_64" --operatingsystem-id="1" --provision-method="build" --build="1" --medium="CentOS mirror" --partition-table="Kickstart default" --root-password="'
        + "DOESNTMATTER"
        + '" --parameters "selinux-mode=permissive, package_upgrade=true, enable-puppetlabs-repo=true, force-puppet=true"'
    )
    print("CMD: hammer host create --name=%s %s" % (node_create, create_str))  # DEBUG
    run_hammer("host create --name=%s %s" % (node_create, create_str))
    # wait some to give the node time to start rebuilding
    time.sleep(300)
    # as in this case we provide ONLY the node hostname on the command line we
    # need to build the FQDN for the playbook
    nodefqdn = node_create + "." + foreman_domain
    # run the Ansible playbook node_add
    run_command(
        'ansible-playbook ansible/node_add.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
        % (nodefqdn, IP)
    )
    # better error handling, if anything fails before this point
    # it will sys.exit(1) and this line will never be printed
    print("Provisioned %s" % nodefqdn)


def func_delete(fqdn_delete):
    # hammer host delete --help
    #
    # get the IP address
    IP = run_command("dig +short @127.0.0.1 %s" % fqdn_delete)
    #
    # hammer host delete --name=testvm.test.mydomain.com
    print("CMD: hammer host delete --name=%s" % fqdn_delete)  # DEBUG
    run_hammer("host delete --name=%s" % fqdn_delete)
    # run the Ansible playbook node_remove
    run_command(
        'ansible-playbook ansible/node_remove.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
        % (fqdn_delete, IP)
    )


def func_info(fqdn_info):
    # hammer host info --help
    #
    # hammer host info --name=testvm.test.mydomain.com
    print("CMD: hammer host info --name=%s" % fqdn_info)  # DEBUG
    run_hammer("host info --name=%s" % fqdn_info)


def func_list():
    # hammer host list --help
    #
    print("CMD: hammer host list")  # DEBUG
    run_hammer("host list")


def func_rebuild(fqdn_rebuild):
    # hammer host update --help
    #
    # get the IP address
    IP = run_command("dig +short @127.0.0.1 %s" % fqdn_rebuild)
    #
    # rebuild consists of three separate tasks
    # 1) mark the host for rebuild in foreman
    # 2) trigger a reboot of the host in +1 min
    # 3) remove the host from known_hosts
    #    both IP and FQDN
    update_str = '--parameters "selinux-mode=permissive, package_upgrade=true, enable-puppetlabs-repo=true, force-puppet=true" --build 1'
    print("CMD: hammer host update %s --name=%s" % (update_str, fqdn_rebuild))  # DEBUG
    run_hammer("host update %s --name=%s" % (update_str, fqdn_rebuild))
    remote_reboot(fqdn_rebuild)
    #
    # delegate this part to Ansible playbook, leaving it here for reference
    # run_command("ssh-keygen -R %s" % fqdn_rebuild)
    # run_command("ssh-keygen -R %s" % IP)
    #
    # run the Ansible playbook node_remove
    run_command(
        'ansible-playbook ansible/node_remove.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
        % (fqdn_rebuild, IP)
    )
    # wait some to give the node time to start rebuilding
    time.sleep(300)
    # run the Ansible playbook node_add
    run_command(
        'ansible-playbook ansible/node_add.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
        % (fqdn_rebuild, IP)
    )


if __name__ == "__main__":
    arg_create, arg_delete, arg_info, arg_list, arg_rebuild = arguments()
    # print("create=%s delete=%s info=%s list=%s rebuild=%s" % (arg_create,
    #                                                           arg_delete,
    #                                                           arg_info,
    #                                                           arg_list,
    #                                                           arg_rebuild))
    # DEBUG

    # in order to reuse the nodes_wrapper script for the heavy lifting
    # each action is now in a separate function
    if arg_create:
        # --create has been requested
        func_create(
            arg_create[0], arg_create[1], arg_create[2], arg_create[3], arg_create[4]
        )
        sys.exit()
    if arg_delete:
        # --delete has been requested
        func_delete(arg_delete[0])
        sys.exit()
    if arg_info:
        # --info has been requested
        func_info(arg_info[0])
        sys.exit()
    if arg_list:
        # --list has been requested
        func_list()
        sys.exit()
    if arg_rebuild:
        # --rebuild has been requested
        func_rebuild(arg_rebuild[0])
        sys.exit()
    # no args have been provided, print a short help
    print("No args provided. Try -h for help.")
    # That's all folks!
