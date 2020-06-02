#!/usr/bin/env python3

import subprocess
import os

from amqp_common import (
    ConnectionParameters, Credentials, EventEmitter,
    Event, EventEmitterOptions, Rate,
    RpcServer, PublisherSync
)


class AgentConfig():
    """DeviceTmateAgent configuration class.

    Args:
    """
    # __slots__ = []
    def __init__(self, broker_username='guest', broker_password='guest',
                 broker_host='localhost', broker_port=5782, broker_vhost='/',
                 broker_event_exchange='amq.topic', broker_rpc_exchange='',
                 tmate_socket_path='/tmp/tmate.sock',
                 hb_event_name='thing.{DEVICE_ID}.tmateagent.heartbeat',
                 start_rpc_name='thing.{DEVICE_ID}.tmateagent.start',
                 stop_rpc_name='thing.{DEVICE_ID}.tmateagent.stop',
                 tunnel_info_rpc_name='thing.{DEVICE_ID}.tmateagent.tunnel_info',
                 heartbeat_interval=2, device_id=None):
        self.broker_params = {
            'username': broker_username,
            'password': broker_password,
            'host': broker_host,
            'port': broker_port,
            'vhost': broker_vhost,
            'event_exchange': broker_event_exchange,
            'rpc_exchange': broker_rpc_exchange
        }
        self.tmate_socket_path = tmate_socket_path
        self.heartbeat_interval = heartbeat_interval
        if device_id is None:
            device_id = broker_username
        self.device_id = device_id
        self.hb_event_name = hb_event_name.replace('{DEVICE_ID}', device_id)
        self.start_rpc_name = start_rpc_name.replace('{DEVICE_ID}', device_id)
        self.stop_rpc_name = stop_rpc_name.replace('{DEVICE_ID}', device_id)
        self.tunnel_info_rpc_name = tunnel_info_rpc_name.replace(
            '{DEVICE_ID}', device_id)

class DeviceTmateAgent():
    """Device tmate agent class.
    Implementation of an AMQP agent that handles ssh tunelling via a tmate
        server. For more information about tmate:
        https://github.com/tmate-io/tmate

    Args:
    """
    def __init__(self, config=None):
        self.ssh_con_str = ''
        self.ssh_con_ro_str = ''

        if config is None:
            config = AgentConfig(broker_host='r4a-platform.ddns.net',
                                 broker_username='device0',
                                 broker_password='k!sh@')
        self.config = config

        self.debug = True

        self._init_broker_endpoints()

    def _init_broker_endpoints(self):
        b_params = self.config.broker_params
        con_params = ConnectionParameters(
            host=b_params['host'], port=b_params['port'],
            vhost=b_params['vhost']
        )
        con_params.credentials = Credentials(b_params['username'],
                                             b_params['password'])
        options = EventEmitterOptions(exchange=b_params['event_exchange'])

        self.hb_em = EventEmitter(
            options,
            connection_params=con_params,
            debug=self.debug
        )

        self.hb_event = Event(name=self.config.hb_event_name,
                              payload={}, headers={})

        self.start_rpc = RpcServer(
            self.config.start_rpc_name,
            on_request=self._start_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.start_rpc.run_threaded()

        self.stop_rpc = RpcServer(
            self.config.stop_rpc_name,
            on_request=self._stop_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.stop_rpc.run_threaded()

        self.tunnel_info_rpc = RpcServer(
            self.config.tunnel_info_rpc_name,
            on_request=self._tunnel_info_rpc_callback,
            connection_params=con_params,
            debug=self.debug)
        self.tunnel_info_rpc.run_threaded()

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

    def _tmate_get_ssh_info(self):
        out = subprocess.check_output(['tmate',  '-S', '/tmp/tmate.sock',
                                       'display', '-p', '\'#{tmate_ssh}\''],
                                      stderr=subprocess.STDOUT)
        return out.decode('utf8').split('\n')[0]

    def _tmate_get_ssh_ro_info(self):
        out = subprocess.check_output(['tmate',  '-S', '/tmp/tmate.sock',
                                       'display', '-p', '\'#{tmate_ssh_ro}\''],
                                      stderr=subprocess.STDOUT)
        return out.decode('utf8').split('\n')[0]

    def _launch_tmate_client_headless(self):
        try:
            out = subprocess.check_output(['tmate',  '-S', self.config.tmate_socket_path,
                                           'new-session', '-d'],
                                          stderr=subprocess.STDOUT)
            out = subprocess.check_output(['tmate',  '-S', self.config.tmate_socket_path,
                                           'wait', 'tmate-ready'],
                                          stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            print('[ERROR]: {} - {}'.format(exc.returncode, exc.output))
            return False
        print('[INFO]: Tmate client Connected!')
        return True

    def run(self):
        rate = Rate(1 / self.config.heartbeat_interval)
        self.start_tmate_client()
        while True:
            # Publish once
            self.hb_em.send_event(self.hb_event)
            rate.sleep()

    def start_tmate_client(self):
        """Start tmate client process.
        The process is spawned in daemon mode and tunnel info are printed
        upon successfull connection with the remote tmate server.
        """
        if os.path.exists(self.config.tmate_socket_path):
            self.stop_tmate_agent()
        _status = self._launch_tmate_client_headless()
        if not _status:
            return
        _out = self._tmate_get_ssh_info()
        self.ssh_con_str = _out
        _out = self._tmate_get_ssh_ro_info()
        self.ssh_con_ro_str = _out
        print('[INFO]: Tunnel info: {}'.format(self.ssh_con_str))
        print('[INFO]: Read-Only Tunnel info: {}'.format(
            self.ssh_con_str))

    def spawn_tmate_client_sh(self):
        """Execute tmate_connect.sh bash script in fork mode."""
        out = subprocess.check_output(['bash', 'tmate_connect.sh'],
                                      stderr=subprocess.STDOUT)
        return out

    def stop_tmate_agent(self):
        """Stops tmate client gracefully.
        Removes local tmate socket.
        """
        if os.path.exists(self.config.tmate_socket_path):
            os.remove(self.config.tmate_socket_path)
        self.ssh_con_str = ''
        self.ssh_con_ro_str = ''

    def parse_sh_script_output(self, out):
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
