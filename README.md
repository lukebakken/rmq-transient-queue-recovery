# Transient queue recovery

## Requirements

- docker
- docker-compose
- python 3.7
- pipenv

## Reproduction steps

1. Clone repo and make it current working directory

2. Start the cluster and wait until all nodes are up and running:

    ```shell
    $ ./start.sh
    Creating network "rmq-transient-queue-recovery_default" with the default driver
    Creating rmq1 ...
    Creating rmq2 ...
    Creating rmq3 ...
    $ docker ps
    CONTAINER ID        IMAGE                                                 COMMAND                  CREATED              STATUS              PORTS                                                                                                                NAMES
    a591dcd47350        rabbitmq:3.7.15-management                            "docker-entrypoint.s…"   34 seconds ago       Up 32 seconds       4369/tcp, 5671/tcp, 15671/tcp, 25672/tcp, 0.0.0.0:5472->5672/tcp, 0.0.0.0:5473->5673/tcp, 0.0.0.0:15472->15672/tcp   rmq3
    b4a8f4e8c54e        rabbitmq:3.7.15-management                            "docker-entrypoint.s…"   56 seconds ago       Up 55 seconds       4369/tcp, 5671/tcp, 15671/tcp, 25672/tcp, 0.0.0.0:5572->5672/tcp, 0.0.0.0:5573->5673/tcp, 0.0.0.0:15572->15672/tcp   rmq2
    22b6a66badf2        rabbitmq:3.7.15-management                            "docker-entrypoint.s…"   About a minute ago   Up About a minute   4369/tcp, 5671/tcp, 0.0.0.0:5672-5673->5672-5673/tcp, 15671/tcp, 25672/tcp, 0.0.0.0:15672->15672/tcp                 rmq1
    ```

    Command creates a cluster of 3 nodes with the following config:

    ```erlang
    [
     {rabbit,
      [
       {cluster_nodes, {['rabbit@rmq1',
                         'rabbit@rmq2',
                         'rabbit@rmq3'], disc}},
       {cluster_partition_handling, autoheal}
      ]
     },

     {rabbitmq_management,
      [
       {load_definitions, "/var/lib/rabbitmq/definitions.json"}
      ]}
    ].
    ```

    And the following policy:

    ``` json
    {
        "vhost": "/",
        "name": "rmq-two",
        "pattern": "^rmq-two-.*$",
        "apply-to": "queues",
        "definition": {
            "ha-mode": "nodes",
            "ha-params": [
                "rabbit@rmq2",
                "rabbit@rmq3"
            ],
            "ha-sync-mode": "automatic"
        },
        "priority": 0
    }
    ```

2. Create a transient queue `rmq-two-queue` and send some messages

    ```shell
    $ ./setup-queue.py -q rmq-two-queue -d -t
    ```

    ![queue](queue.png "Queue")


3. Gracefully stop `rmq2`

    ```shell
    $ docker stop rmq2
    ```

4. Note that queue on node `rmq3` was promoted to master

    ```
    rmq3    | 2019-06-27 09:18:31.068 [info] <0.943.0> Mirrored queue 'rmq-two-queue' in vhost '/': Promoting slave <rabbit@rmq3.3.943.0> to master
    ```

5. Gracefully stop `rmq3`

6. Note master shutdown on `rmq3`

    ```
    rmq3    | 2019-06-27 09:20:59.926 [warning] <0.943.0> Mirrored queue 'rmq-two-queue' in vhost '/': Stopping all nodes on master shutdown since no synchronised slave is available
    ```

7. Start `rmq3`

8. Note `pid` reference did not change on nodes `rmq1` and `rmq3`

    See "Queue states" section below for details.

9. Try to list queues on node `rmq1` (or `rmq3`)

    ```shell
    $ docker exec -it rmq1 rabbitmqctl list_queues name pid slave_pids synchronised_slave_pids
    Timeout: 60.0 seconds ...
    Listing queues for vhost / ...

    09:26:25.793 [error] Discarding message {'$gen_call',{<0.753.0>,#Ref<0.989368845.173015041.56949>},{info,[name,pid,slave_pids,synchronised_slave_pids]}} from <0.753.0> to <0.943.0> in an old incarnation (3) of this node (1)
    ```

10. Start `rmq2`
11. Note queue has not been recovered, `pid` on all nodes refer to old incarnation of the queue (before `rmq3` shutdown).

12. Try to list queues again

    ```
    $ docker exec -it rmq1 rabbitmqctl list_queues name pid slave_pids synchronised_slave_pids
    Timeout: 60.0 seconds ...
    Listing queues for vhost / ...

    09:31:08.102 [error] Discarding message {'$gen_call',{<0.928.0>,#Ref<0.989368845.173015041.62682>},{info,[name,pid,slave_pids,synchronised_slave_pids]}} from <0.928.0> to <0.943.0> in an old incarnation (3) of this node (1)
    ```


## Queue states

### All nodes are up

#### `rmq1`

``erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <5879.1110.0>,
          slave_pids = [<5880.943.0>],
          sync_slave_pids = [<5880.943.0>],
          recoverable_slaves = [rabbit@rmq3],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,
          gm_pids = [{<5880.944.0>,<5880.943.0>},
                     {<5879.1111.0>,<5879.1110.0>}],
          decorators = [],state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

#### `rmq2`

``erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <0.1110.0>,
          slave_pids = [<5880.943.0>],
          sync_slave_pids = [<5880.943.0>],
          recoverable_slaves = [rabbit@rmq3],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,
          gm_pids = [{<5880.944.0>,<5880.943.0>},
                     {<0.1111.0>,<0.1110.0>}],
          decorators = [],state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

#### `rmq3`

``erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <5879.1110.0>,
          slave_pids = [<0.943.0>],
          sync_slave_pids = [<0.943.0>],
          recoverable_slaves = [rabbit@rmq3],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,
          gm_pids = [{<0.944.0>,<0.943.0>},
                     {<5879.1111.0>,<5879.1110.0>}],
          decorators = [],state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``




### `rmq2` is down

#### `rmq1`

`` erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <5880.943.0>,slave_pids = [],
          sync_slave_pids = [],recoverable_slaves = [],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,
          gm_pids = [{<5880.944.0>,<5880.943.0>}],
          decorators = [],state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

#### `rmq3`

`` erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <0.943.0>,slave_pids = [],
          sync_slave_pids = [],recoverable_slaves = [],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,
          gm_pids = [{<0.944.0>,<0.943.0>}],
          decorators = [],state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

### `rmq2` and `rmq3` are down

#### `rmq1`

`` erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <5880.943.0>,slave_pids = [],
          sync_slave_pids = [],recoverable_slaves = [],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,gm_pids = [],decorators = [],
          state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

### `rmq3` is up

#### `rmq1`

`` erlang
#amqqueue{name = #resource{virtual_host = <<"/">>,
                           kind = queue,name = <<"rmq-two-queue">>},
          durable = false,auto_delete = false,exclusive_owner = none,
          arguments = [],pid = <5880.943.0>,slave_pids = [],
          sync_slave_pids = [],recoverable_slaves = [],
          policy = [{vhost,<<"/">>},
                    {name,<<"rmq-two">>},
                    {pattern,<<"^rmq-two-.*$">>},
                    {'apply-to',<<"queues">>},
                    {definition,[{<<"ha-mode">>,<<"nodes">>},
                                 {<<"ha-params">>,
                                  [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                 {<<"ha-sync-mode">>,<<"automatic">>}]},
                    {priority,0}],
          operator_policy = undefined,gm_pids = [],decorators = [],
          state = live,policy_version = 0,
          slave_pids_pending_shutdown = [],vhost = <<"/">>,
          options = #{user => <<"guest">>}}]
``

#### `rmq3`

``` erlang
[#amqqueue{name = #resource{virtual_host = <<"/">>,
                            kind = queue,name = <<"rmq-two-queue">>},
           durable = false,auto_delete = false,exclusive_owner = none,
           arguments = [],pid = <0.943.0>,slave_pids = [],
           sync_slave_pids = [],recoverable_slaves = [],
           policy = [{vhost,<<"/">>},
                     {name,<<"rmq-two">>},
                     {pattern,<<"^rmq-two-.*$">>},
                     {'apply-to',<<"queues">>},
                     {definition,[{<<"ha-mode">>,<<"nodes">>},
                                  {<<"ha-params">>,
                                   [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                  {<<"ha-sync-mode">>,<<"automatic">>}]},
                     {priority,0}],
           operator_policy = undefined,gm_pids = [],decorators = [],
           state = live,policy_version = 0,
           slave_pids_pending_shutdown = [],vhost = <<"/">>,
           options = #{user => <<"guest">>}}]
```

#### `rmq1`

``` erlang
[#amqqueue{name = #resource{virtual_host = <<"/">>,
                            kind = queue,name = <<"rmq-two-queue">>},
           durable = false,auto_delete = false,exclusive_owner = none,
           arguments = [],pid = <5880.943.0>,
           slave_pids = [<5879.453.0>],
           sync_slave_pids = [],recoverable_slaves = [],
           policy = [{vhost,<<"/">>},
                     {name,<<"rmq-two">>},
                     {pattern,<<"^rmq-two-.*$">>},
                     {'apply-to',<<"queues">>},
                     {definition,[{<<"ha-mode">>,<<"nodes">>},
                                  {<<"ha-params">>,
                                   [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                  {<<"ha-sync-mode">>,<<"automatic">>}]},
                     {priority,0}],
           operator_policy = undefined,
           gm_pids = [{<5879.454.0>,<5879.453.0>}],
           decorators = [],state = live,policy_version = 0,
           slave_pids_pending_shutdown = [],vhost = <<"/">>,
           options = #{user => <<"guest">>}}]
```
#### `rmq2`

``` erlang
[#amqqueue{name = #resource{virtual_host = <<"/">>,
                            kind = queue,name = <<"rmq-two-queue">>},
           durable = false,auto_delete = false,exclusive_owner = none,
           arguments = [],pid = <5880.943.0>,
           slave_pids = [<0.453.0>],
           sync_slave_pids = [],recoverable_slaves = [],
           policy = [{vhost,<<"/">>},
                     {name,<<"rmq-two">>},
                     {pattern,<<"^rmq-two-.*$">>},
                     {'apply-to',<<"queues">>},
                     {definition,[{<<"ha-mode">>,<<"nodes">>},
                                  {<<"ha-params">>,
                                   [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                  {<<"ha-sync-mode">>,<<"automatic">>}]},
                     {priority,0}],
           operator_policy = undefined,
           gm_pids = [{<0.454.0>,<0.453.0>}],
           decorators = [],state = live,policy_version = 0,
           slave_pids_pending_shutdown = [],vhost = <<"/">>,
           options = #{user => <<"guest">>}}]
```

#### `rmq3`

``` erlang
[#amqqueue{name = #resource{virtual_host = <<"/">>,
                            kind = queue,name = <<"rmq-two-queue">>},
           durable = false,auto_delete = false,exclusive_owner = none,
           arguments = [],pid = <0.943.0>,
           slave_pids = [<5879.453.0>],
           sync_slave_pids = [],recoverable_slaves = [],
           policy = [{vhost,<<"/">>},
                     {name,<<"rmq-two">>},
                     {pattern,<<"^rmq-two-.*$">>},
                     {'apply-to',<<"queues">>},
                     {definition,[{<<"ha-mode">>,<<"nodes">>},
                                  {<<"ha-params">>,
                                   [<<"rabbit@rmq2">>,<<"rabbit@rmq3">>]},
                                  {<<"ha-sync-mode">>,<<"automatic">>}]},
                     {priority,0}],
           operator_policy = undefined,
           gm_pids = [{<5879.454.0>,<5879.453.0>}],
           decorators = [],state = live,policy_version = 0,
           slave_pids_pending_shutdown = [],vhost = <<"/">>,
           options = #{user => <<"guest">>}}]
```
