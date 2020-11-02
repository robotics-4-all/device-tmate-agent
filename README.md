# device-tmate-agent
Agent around tmate to remotely connect to devices via ssh. 

![Architecture](/tmate2.png)

## Provided Interfaces

The daemon connects to a remote AMQP broker and provides various control and monitoring interfaces.
The AMQP broker parameters can be configured via the `~/.config/device_tmate_agent/config` file. This config file is loaded
on startup.

### Control Interfaces

#### Get Tunnel Info RPC

**URI**: `thing.{thing_id}.tmageagent.tunnel_info`

**DataModel**:

```json
Request
--------

{}

Response
--------

{
  'status': <int>,
  'error': <str>,
  'tunnel_info': <str>
}
```

A call to this RPC returns the required information to perform remote ssh connection to the device.

#### Restart Tunnel RPC

**URI**: `thing.{thing_id}.tmageagent.restart`

**DataModel**:

```json
Request
--------

{}

Response
--------

{
  'status': <int>,
  'error': <str>,
  'tunnel_info': <str>
}
```

A call to this RPC forces a restart of the tunnel session and returns the new tunnel information.

#### Start RPC

**URI**: `thing.{thing_id}.tmageagent.start`

**DataModel**:

```json
Request
--------

{}

Response
--------

{
  'status': <int>,
  'error': <str>,
  'tunnel_info': <str>
}
```

#### Stop RPC

**URI**: `thing.{thing_id}.tmageagent.stop`

**DataModel**:

```json
Request
--------

{}

Response
--------

{
  'status': <int>,
  'error': <str>
}
```

### Monitoring Interfaces

#### Heartbeats

Heartbeats are sent (by default) to the `thing.{thing_id}.tmateagent.heartbeat` topic with a frequency of 0.1Hz (by default).

**Data Model**

```json
{
  'timestamp': <float>
}
```
