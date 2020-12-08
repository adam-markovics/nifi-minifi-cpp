# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the \"License\"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an \"AS IS\" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from minifi import *

def test_publish_mqtt():
    """
    Verify delivery of message to MQTT broker
    """
    producer_flow = GetFile('/tmp/input') >> PublishMQTT() \
                        >> (('failure', LogAttribute()),
                            ('success', PutFile('/tmp/output/success')))

    with DockerTestCluster(SingleFileOutputValidator('test', subdir='success')) as cluster:
        cluster.put_test_data('test')
        cluster.deploy_flow(None, engine='mqtt-broker')
        cluster.deploy_flow(producer_flow, name='minifi-producer', engine='minifi-cpp')
        cluster.wait_for_container_logs('mqtt-broker', 'Received PUBLISH from .*testtopic.*\\(4 bytes\\)', 10, 1, True)

        assert cluster.check_output(30)

def test_no_broker():
    """
    Verify failure case when broker is down
    """
    #TODO: failure and success should be handled together
    producer_flow = (GetFile('/tmp/input') >> PublishMQTT()
                        >> (('failure', PutFile('/tmp/output')),
                            ('success', PutFile('/tmp/output'))))

    with DockerTestCluster(SingleFileOutputValidator(None)) as cluster:
        cluster.put_test_data('no broker')
        cluster.deploy_flow(producer_flow, name='minifi-producer', engine='minifi-cpp')

        assert cluster.check_output(30)

def test_broker_on_off():
    """
    Verify delivery of message when broker is unstable
    """
    producer_flow = (GetFile('/tmp/input') >> PublishMQTT()
                     >> (('success', PutFile('/tmp/output/success')),
                         ('failure', PutFile('/tmp/output/failure'))))

    with DockerTestCluster(SingleFileOutputValidator('test')) as cluster:
        # start
        cluster.put_test_data('test')
        cluster.deploy_flow(None, engine='mqtt-broker')
        cluster.deploy_flow(producer_flow, name='minifi-producer', engine='minifi-cpp')
        cluster.wait_for_container_logs('mqtt-broker', 'Received PUBLISH from .*testtopic.*\\(4 bytes\\)', 10, 1, True)
        assert cluster.check_output(30, subdir='success')

        # stop
        assert cluster.stop_flow('mqtt-broker')
        cluster.rm_out_child('success')
        cluster.output_validator.expected_content = None
        assert cluster.check_output(30, subdir='success')
        assert cluster.check_output(30, subdir='failure')
        cluster.output_validator.expected_content = 'test'

        # start
        assert cluster.start_flow('mqtt-broker')
        assert cluster.check_output(30, subdir='success')

        # stop
        assert cluster.stop_flow('mqtt-broker')
        cluster.rm_out_child('success')
        cluster.output_validator.expected_content = None
        assert cluster.check_output(30, subdir='success')
        assert cluster.check_output(30, subdir='failure')
