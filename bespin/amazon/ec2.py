from bespin.helpers import memoized_property

import boto.ec2
import boto.ec2.autoscale

import datetime
import logging

log = logging.getLogger("bespin.amazon.ec2")

class EC2(object):
    def __init__(self, region="ap-southeast-2"):
        self.region = region

    @memoized_property
    def conn(self):
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
        self.autoscale.suspend_processes(asg_physical_id, ["ScheduledActions"])

    def suspend_processes(self, asg_physical_id):
        self.autoscale.suspend_processes(asg_physical_id, ["ScheduledActions"])

    def display_instances(self, asg_physical_id, instance=None):
        log.info("Finding instances")
        instance_ids = []
        if asg_physical_id:
            asg = self.autoscale.get_all_groups(names=[asg_physical_id])
            instance_ids = [inst.instance_id for inst in asg[0].instances]
        elif instance:
            instance_ids = [instance]

        print("Found {0} instances".format(len(instance_ids)))
        print("=" * 20)
        if instance_ids:
            for instance in self.conn.get_only_instances(instance_ids=instance_ids):
                launch_time = datetime.datetime.strptime(instance.launch_time, '%Y-%m-%dT%H:%M:%S.000Z')
                delta = (datetime.datetime.utcnow() - launch_time).seconds
                print("{0}\t{1}\t{2}\tUp {3} seconds".format(instance.id, instance.private_ip_address, instance.state, delta))

