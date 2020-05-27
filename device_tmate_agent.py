#!/usr/bin/env python3

import subprocess
import os

from amqp_common import (
    ConnectionParameters, Credentials, EventEmitter,
    Event, EventEmitterOptions, Rate,
    RpcServer, PublisherSync
)


class DeviceTmateAgent():
    """Device tmate agent class.
    Implementation of an AMQP agent that handles ssh tunelling via a tmate
        server. For more information about tmate:
        https://github.com/tmate-io/tmate

    Args:
    """
    def __init__(self):
        self.ssh_con_str = ''
        self.ssh_con_ro_str = ''

        self.tmate_sock_path = '/tmp/tmate.sock'

        self.username = 'device0'
        self.password = 'device0'
        self.host = 'r4a-platform.ddns.net'
        self.port = 5782
        self.vhost = '/'
        self.hb_event_id = 'thing.{}.tmateagent.heartbeat'.format(
            self.username)
        self.start_rpc_name = 'thing.x.tmateagent.start'.replace(
            'x', self.username)
        self.stop_rpc_name = 'thing.x.tmateagent.stop'.replace(
            'x', self.username)
        self.tunnel_info_rpc_name = 'thing.x.tmateagent.tunnel_info'.replace(
            'x', self.username)
        self.tunnel_info_topic = 'thing.x.tmateagent.tunnel_info'.replace(
            'x', self.username)
        self.debug = True
        self.hz = 1
        con_params = ConnectionParameters(host=self.host, port=self.port,
                                          vhost=self.vhost)
        con_params.credentials = Credentials(self.username, self.password)
        options = EventEmitterOptions(exchange='amq.topic')

        self.hb_em = EventEmitter(
            options,
            connection_params=con_params,
            debug=self.debug
        )

        self.hb_event = Event(name=self.hb_event_id, payload={}, headers={})

        self.start_rpc = RpcServer(
            self.start_rpc_name,
            on_request=self._start_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.start_rpc.run_threaded()

        self.stop_rpc = RpcServer(
            self.stop_rpc_name,
            on_request=self._stop_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.stop_rpc.run_threaded()

        self.tunnel_info_rpc = RpcServer(
            self.tunnel_info_rpc_name,
            on_request=self._tunnel_info_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.tunnel_info_rpc.run_threaded()

        self.pub = PublisherSync(
            self.tunnel_info_topic,
            connection_params=con_params,
            debug=self.debug
        )

    def _start_rpc_callback(self, msg, meta):
        print('[DEBUG] - Start RPC Call')
        try:
            self.start_tmate_client()
        except Exception as exc:
            pass
        response = {
            'ssh': self.ssh_con_str,
            'ssh_ro': self.ssh_con_ro_str
        }
        return response

    def _stop_rpc_callback(self, msg, meta):
        print('[DEBUG] - STOP RPC Call')
        status = 200
        error = ''
        try:
            self.stop_tmate_agent()
        except Exception as exc:
            status = 500
            error = exc
        response = {
            'status': status,
            'error': str(exc)
        }
        return response

    def _tunnel_info_rpc_callback(self, msg, meta):
        return self._get_tunnel_info()

    def _publish_tunnel_info(self):
        self.pub.publish(self._get_tunnel_info())

    def _get_tunnel_info(self):
        _info = {
            'ssh': self.ssh_con_str,
            'ssh_ro': self.ssh_con_ro_str
        }
        return _info

    def run(self):
        rate = Rate(self.hz)
        self.start_tmate_client()
        while True:
            # Publish once
            self.hb_em.send_event(self.hb_event)
            self._publish_tunnel_info()
            rate.sleep()

    def start_tmate_client(self):
        out = self.spawn_tmate_client()
        self.parse_output(out)

    def spawn_tmate_client(self):
        out = subprocess.check_output(['bash', 'tmate_connect.sh'],
                                      stderr=subprocess.STDOUT)
        return out

    def stop_tmate_agent(self):
        os.remove(self.tmate_sock_path)

    def parse_output(self, out):
        out = out.decode('utf8').split('\n')
        if 'create session failed' in out[0]:
            print('[WARN] - {}'.format(out[0]))
            ssh_con_str = out[1]
            ssh_con_ro_str = out[2]
        else:
            ssh_con_str = out[0]
            ssh_con_ro_str = out[1]
        print('[INFO] - SSH Session String <{}>'.format(ssh_con_str))
        print('[INFO] - SSH RO Session String <{}>'.format(ssh_con_ro_str))
        self.ssh_con_str = ssh_con_str
        self.ssh_con_ro_str = ssh_con_ro_str


if __name__ == '__main__':
    agent = DeviceTmateAgent()
    agent.run()
