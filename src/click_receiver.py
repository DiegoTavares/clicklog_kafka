import os
import time
import io

# pyspark and kafka
from pyspark import SparkContext, SparkConf
from pyspark.sql import SQLContext, Row
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils

# avro
import avro
import avro.schema
from avro.io import DatumWriter, DatumReader
from avro.datafile import DataFileReader

os.environ['PYSPARK_SUBMIT_ARGS'] = '--conf spark.ui.port=4040 --packages org.apache.spark:spark-streaming-kafka_2.11:1.6.1,com.datastax.spark:spark-cassandra-connector_2.11:1.6.0-M2 pyspark-shell'
# Read schema and create reader
schema = avro.schema.parse(open("data/click_log.avsc").read())
reader = avro.io.DatumReader(schema)

# Start SparkContext and SQLContext
# Due to lib constraints, they need to be instantiated in the global scope
conf = SparkConf().setAppName("Streaming Clicks") \
                  .setMaster("local[2]") \
                  .set("spark.cassandra.connection.host", "127.0.0.1")
sc = SparkContext(conf=conf)
sqlContext = SQLContext(sc)


def decoder(binary_item):
    """To obtain a rdd row, decode a binary item.
    This function cannot be placed inside the class due to serialization
    problems"""
    decoded = reader.read(avro.io.BinaryDecoder(io.BytesIO(binary_item)))
    return Row(user_id=decoded['user_id'],
               time=decoded['time'],
               action=decoded['action'],
               destination=decoded['destination'],
               hotel=decoded['hotel'])


class ClickReceiver:
    """ Receiver for a kafka topic containing user clicks stored in the avro
    format data/click_log.avsc.

    click actions can be:
        1 = search
        2 = filter
        3 = click
    """
    def __init__(self, kafka_topic, batchDuration):
        self.checkpointDirectory = "data/ssc_checkpoint"
        self.batchDuration = batchDuration
        self.kafka_topic = kafka_topic  # clicklog
        self.ssc = self.createStreamingContext()

    def setup(self, actions):
        """Execute a list of actions in every stream block"""
        kvs = KafkaUtils.createStream(self.ssc,
                                      "127.0.0.1:2181",
                                      "spark-streaming-consumer",
                                      {self.kafka_topic: 1},
                                      valueDecoder=decoder)
        click_rdd = kvs.map(lambda x: x[1])
        # click_rdd.pprint()  # Uncomment this line to see the raw output
        for action in actions:
            action(click_rdd)

    def start(self):
        """Start the streaming process"""
        self.ssc.start()

    def createStreamingContext(self):
        """To obtain a spark streaming context, create a spark context and set the
           checkpoint directory"""
        ssc = StreamingContext(sc, self.batchDuration)
        ssc.checkpoint(self.checkpointDirectory)   # set checkpoint directory
        return ssc
