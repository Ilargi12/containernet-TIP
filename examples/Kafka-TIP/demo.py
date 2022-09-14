from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel
from time import sleep
from sys import argv

setLogLevel('info')

NUM_TOPICS = int(argv[1])
NUM_RECORDS = int(argv[2])
RECORD_SIZE = int(argv[3])
PRODUCER_THROUGHPUT = int(argv[4])
TEST_INTERVAL_SECONDS = int(argv[5])

net = Containernet(controller=Controller)
net.addController('c0')

info('*** Adding Zookeeper\n')
zookeeper = net.addDocker('zookeeper', ip='10.0.0.251',
                       dimage="confluentinc/cp-zookeeper:7.0.1",
                       environment={"ZOOKEEPER_CLIENT_PORT": 2181,
                                    "ZOOKEEPER_TICK_TIME": 2000},
                       ports=[2181],
                       port_bindings={2181:2181})

info('*** Adding Kafka broker\n')
broker = net.addDocker('broker',ip='10.0.0.252',
                       dimage="confluentinc/cp-kafka:7.0.1",
                       environment={"KAFKA_BROKER_ID": 1,
                                    "KAFKA_ZOOKEEPER_CONNECT": 'zookeeper:2181',
                                    "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT,PLAINTEXT_INTERNAL:PLAINTEXT",
                                    "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://broker:29092",
                                    "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": 1,
                                    "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": 1,
                                    "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": 1},
                       ports=[9092],
                       port_bindings={9092:9092})

generator = net.addDocker('generator', ip='10.0.0.253',
                            dimage='kafka-generator',
                            environment={"BOOTSTRAP_SERVERS":"http://localhost:9092"})

# info('*** Adding producer and consumer\n')
# consumer = net.addDocker('consumer', ip='10.0.0.253',
#                          dimage="kafka-consumer")
# producer = net.addDocker('producer', ip='10.0.0.254',
#                          dimage="kafka-producer")


info('*** Setup network\n')
s1 = net.addSwitch('s1')
net.addLink(zookeeper, s1)
net.addLink(broker, s1)
net.addLink(generator, s1)
# net.addLink(consumer, s2)
# net.addLink(producer, s2)

net.start()

info('*** Starting server\n')
info("*** Waiting 50 sec to start server...\n")
zookeeper.start()
broker.start()

sleep(50)

info("*** Printing server IP:PORT to reach UI\n")
info(zookeeper.cmd("netstat -an | grep 2181 | grep ESTABLISHED | awk -F ' ' '{print $4}'"))
info(broker.cmd("netstat -an | grep 9092 | grep ESTABLISHED | awk -F ' ' '{print $4}'"))

info('*** Starting perf-test\n')

info(generator.cmd(f"python scripts/producer_test.sh {NUM_TOPICS} {NUM_RECORDS} {RECORD_SIZE} {PRODUCER_THROUGHPUT} {TEST_INTERVAL_SECONDS} -o output_prod.csv"))
info(generator.cmd(f"python scripts/consumer_test.sh {NUM_TOPICS} {NUM_RECORDS} {RECORD_SIZE} {PRODUCER_THROUGHPUT} {TEST_INTERVAL_SECONDS} -o output_con.csv"))

info('*** Starting to execute commands\n')

sleep(5)

CLI(net)

net.stop()