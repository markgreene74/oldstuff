#!/usr/bin/env python
"""
Provide a wrapper for creating/printing info/deleting nodes using hammer-cli
"""

import argparse
import subprocess
import sys
import time


def arguments():
    """
    Parse arguments and return help message
    """
    helper_version = "0.1"
    helper_descr = "Wrapper for hammer-cli/Foreman nodes"
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


def run_hammer(hmmr_args):
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
    print("hammer-cli output: \n%s" % hr_result)
    if error:
        sys.stderr.write("hammer-cli error: %s\n" % hr_error)
        sys.exit(1)
    return hr_result


def run_command(run_args, wd=None):
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
    print("CMD output: \n%s" % hr_result)
    if error:
        sys.stderr.write("CMD error: %s\n" % hr_error)
        sys.exit(1)
    return hr_result


if __name__ == "__main__":
    arg_create, arg_delete, arg_info, arg_list, arg_rebuild = arguments()
    # print("create=%s delete=%s info=%s list=%s rebuild=%s" % (arg_create,
    #                                                           arg_delete,
    #                                                           arg_info,
    #                                                           arg_list,
    #                                                           arg_rebuild))
    # DEBUG

    if arg_create:
        # --create has been requested
        # hammer host create --help
        #
        # print(arg_create)  # DEBUG
        # create needs 5 args: hostname, IP, vCPU, memory (GB), disk (GB)
        # example:
        # --create testvm 192.168.1.200 1 2 10
        # hammer host create (...) --name=testvm.test.mydomain.com
        #
        # gather information from the foreman server:
        # we need the FQDN and the domain, example:
        # [foreman.[test.mydomain.com]]
        foreman_fqdn = run_command("hostname -f").strip()
        foreman_domain = run_command("hostname -d").strip()
        # assign args to variables
        IP = arg_create[1]
        vCPU = arg_create[2]
        memory = str(int(arg_create[3]) * 1073741824)
        disk = arg_create[4]
        # NOTE: memory has to be a string representing the number in bytes
        # for example: 2 GB correspond to 2147483648
        # 2 * 1024 * 1024 * 1024
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
        print(
            "CMD: hammer host create --name=%s %s" % (arg_create[0], create_str)
        )  # DEBUG
        run_hammer("host create --name=%s %s" % (arg_create[0], create_str))
        # wait some to give the node time to start rebuilding
        time.sleep(300)
        # as in this case we provide ONLY the node hostname on the command line we
        # need to build the FQDN for the playbook
        nodefqdn = arg_create[0] + "." + foreman_domain
        # run the Ansible playbook node_add
        run_command(
            'ansible-playbook ansible/node_add.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
            % (nodefqdn, IP)
        )
        sys.exit()
    if arg_delete:
        # --delete has been requested
        # hammer host delete --help
        #
        # get the IP address
        IP = run_command("dig +short @127.0.0.1 %s" % arg_delete[0])
        #
        # hammer host delete --name=testvm.test.mydomain.com
        print("CMD: hammer host delete --name=%s" % arg_delete[0])  # DEBUG
        run_hammer("host delete --name=%s" % arg_delete[0])
        # run the Ansible playbook node_remove
        run_command(
            'ansible-playbook ansible/node_remove.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
            % (arg_delete[0], IP)
        )
        sys.exit()
    if arg_info:
        # --info has been requested
        # hammer host info --help
        #
        # hammer host info --name=testvm.test.mydomain.com
        print("CMD: hammer host info --name=%s" % arg_info[0])  # DEBUG
        run_hammer("host info --name=%s" % arg_info[0])
        sys.exit()
    if arg_list:
        # --list has been requested
        # hammer host list --help
        #
        print("CMD: hammer host list")  # DEBUG
        run_hammer("host list")
        sys.exit()
    if arg_rebuild:
        # --rebuild has been requested
        # hammer host update --help
        #
        # get the IP address
        IP = run_command("dig +short @127.0.0.1 %s" % arg_rebuild[0])
        #
        # rebuild consists of three separate tasks
        # 1) mark the host for rebuild in foreman
        # 2) trigger a reboot of the host in +1 min
        # 3) remove the host from known_hosts
        #    both IP and FQDN
        update_str = '--parameters "selinux-mode=permissive, package_upgrade=true, enable-puppetlabs-repo=true, force-puppet=true" --build 1'
        print(
            "CMD: hammer host update %s --name=%s" % (update_str, arg_rebuild[0])
        )  # DEBUG
        run_hammer("host update %s --name=%s" % (update_str, arg_rebuild[0]))
        remote_reboot(arg_rebuild[0])
        #
        # delegate this part to Ansible playbook, leaving it here for reference
        # run_command("ssh-keygen -R %s" % arg_rebuild[0])
        # run_command("ssh-keygen -R %s" % IP)
        #
        # run the Ansible playbook node_remove
        run_command(
            'ansible-playbook ansible/node_remove.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
            % (arg_rebuild[0], IP)
        )
        # wait some to give the node time to start rebuilding
        time.sleep(300)
        # run the Ansible playbook node_add
        run_command(
            'ansible-playbook ansible/node_add.yaml --extra-vars "node_fqdn=%s node_ip=%s"'
            % (arg_rebuild[0], IP)
        )
        sys.exit()
    # no args have been provided, print a short help
    print("No args provided. Try -h for help.")
    # That's all folks!
