import os
import io
import random
import time
import sys
from kafka import KafkaProducer, KafkaClient
import avro.schema
from avro.io import DatumWriter
from avro.datafile import DataFileReader, DataFileWriter

os.environ['PYSPARK_SUBMIT_ARGS'] = '--conf spark.ui.port=4041 --packages org.apache.kafka:kafka_2.11:0.9.0.0,org.apache.kafka:kafka-clients:0.9.0.0  pyspark-shell'


def main(argv):
    # clicklog producer code
    producer = KafkaProducer(bootstrap_servers='localhost:9092')
    topic = "clicklog"
    msg_per_second = 10

    # Load schema
    schema_path = "data/click_log.avsc"
    schema = avro.schema.parse(open(schema_path).read())

    # Write messages in the avro format and send them to the kafka topic
    writer = avro.io.DatumWriter(schema)
    while True:
        bytes_writer = io.BytesIO()
        encoder = avro.io.BinaryEncoder(bytes_writer)
        writer.write({
                      "user_id": random.randint(0, 1000000),
                      "time": int(time.time()),
                      "action": random.randint(0, 3),
                      "destination": random.randint(0, 10000),
                      "hotel": random.randint(0, 1000)}, encoder)

        producer.send(topic, bytes_writer.getvalue())
        time.sleep(1/msg_per_second)
    writer.close()

if __name__ == "__main__":
    main(sys.argv)
