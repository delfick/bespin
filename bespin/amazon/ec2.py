from bespin.helpers import memoized_property

import boto.ec2
import boto.ec2.autoscale

from input_algorithms.spec_base import NotSpecified
import datetime
import logging

log = logging.getLogger("bespin.amazon.ec2")

class EC2(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
        log.info("Using region [%s] for ec2", self.region)
        return boto.ec2.connect_to_region(self.region)

    @memoized_property
    def autoscale(self):
        return boto.ec2.autoscale.connect_to_region(self.region)

    def get_instances_in_asg_by_lifecycle_state(self, asg_physical_id, lifecycle_state=None):
        instances = []

        asg = self.autoscale.get_all_groups(names=[asg_physical_id])
        for instance in asg[0].instances:
            if lifecycle_state is None or lifecycle_state == instance.lifecycle_state:
                instances.append(instance.instance_id)

        return instances

    def resume_processes(self, asg_physical_id):
        self.autoscale.resume_processes(asg_physical_id, ["ScheduledActions"])

    def suspend_processes(self, asg_physical_id):
        self.autoscale.suspend_processes(asg_physical_id, ["ScheduledActions"])

    def instance_ids_in_autoscaling_group(self, asg_physical_id):
        asg = self.autoscale.get_all_groups(names=[asg_physical_id])
        return [inst.instance_id for inst in asg[0].instances]

    def ips_for_instance_ids(self, instance_ids):
        for instance in self.instances(instance_ids):
            yield instance.private_ip_address

    def instances(self, instance_ids):
        if instance_ids:
            for instance in self.conn.get_only_instances(instance_ids=instance_ids):
                yield instance

    def display_instances(self, instance_ids, address=NotSpecified):
        print("Found {0} instances".format(len(instance_ids)))
        print("=" * 20)
        for instance in self.instances(instance_ids):
            launch_time = datetime.datetime.strptime(instance.launch_time, '%Y-%m-%dT%H:%M:%S.000Z')
            delta = (datetime.datetime.utcnow() - launch_time).seconds
            ip_address = instance.private_ip_address
            if address is not NotSpecified:
                ip_address = address
            print("{0}\t{1}\t{2}\tUp {3} seconds".format(instance.id, ip_address, instance.state, delta))

    def num_alive_instances(self, instance_ids):
        return sum(1 for instance in self.instances(instance_ids)
            if instance.private_ip_address
            )
