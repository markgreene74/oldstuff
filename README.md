# smallprojects

## failed_disk.py [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

Pull information about the failed disk(s) directly from a server (via omreport) and from the disk test in the monitoring system (xymon).
Based on the args print templates to raise an internal ticket, raise a ticket with the datacenter tech, raise a request to buy more disks.
Follow the rebuilding of the disk by polling the server every 60s.

## hammer-cli-wrapper.py [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](    https://github.com/ambv/black)

Provide a nice wrapper for creating/deleting nodes and showing nodes information using hammer-cli.
