#!/usr/bin/env python

import pika
import time
import sys
import random
import functools
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description='Publish messages to a specified host.')
    parser.add_argument('-H', '--host', default='localhost',
                        help='Target host')
    parser.add_argument('-P', '--port', default=5672, type=int)
    parser.add_argument('-q', '--queue', default='test-queue',
                        help='Queue name')
    parser.add_argument('-t', '--transient', default=False,
                        action='store_true')
    parser.add_argument('-d', '--declare', default=False,
                        action='store_true')
    parser.add_argument('-Q', '--queue-argument', action='append', default=[],
                        help='= separated list of headers')
    parser.add_argument('-u', '--user', default='guest')
    parser.add_argument('-p', '--pwd', default='guest')
    parser.add_argument('-s', '--size', type=int, help='Body size in bytes')
    parser.add_argument('-m', '--messages', default=1000, type=int,
                        help='Number of messages to send')
    return parser.parse_args()

def connect(host, port, user, pwd):
    creds = pika.PlainCredentials(user, pwd)
    params = pika.ConnectionParameters(
        host=host, port=port, credentials=creds)
    return pika.BlockingConnection(params)

def queue_declare(channel, queue_name, args=None, **opts):
    channel.queue_declare(queue_name, arguments=args, **opts)

def parse_arguments(args):
    return dict([arg.split('=') for arg in args])

def body(size):
    return ''.join(random.choice(string.ascii_uppercase + string.digits)
                   for _ in range(size))

def publish(channel, queue, payload):
    props = pika.BasicProperties(delivery_mode=2)
    channel.basic_publish(
        exchange='', routing_key=queue, body=payload,
        properties=props)


def main():
    args = parse_args()
    try:
        with connect(args.host, args.port, args.user, args.pwd) as connection:
            channel = connection.channel()
            queue_name = args.queue
            if args.declare:
                queue_arguments = parse_arguments(args.queue_argument)
                queue_declare(
                    channel, queue_name, args=queue_arguments,
                    durable=not args.transient)

            msg = 'Hello World!' if not args.size else body(args.size)
            for _ in range(args.messages):
                publish(channel, queue_name, msg)
    except (pika.exceptions.ConnectionClosed, pika.exceptions.AMQPConnectionError,
            pika.exceptions.ChannelClosedByBroker) as e:
        print(f'trying to reconnect: {e}')
        time.sleep(random.randrange(1, 10) / 10)
    except KeyboardInterrupt:
        connection.close()
        exit(0)

if __name__ == '__main__':
    main()
