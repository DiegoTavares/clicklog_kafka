import click_receiver
from click_receiver import ClickReceiver
from pyspark.sql import SQLContext
from pyspark.sql.functions import from_unixtime
import os
import avro
import avro.schema
from datetime import date, timedelta
from collections import namedtuple

os.environ['PYSPARK_SUBMIT_ARGS'] = '--conf spark.ui.port=4040 --packages org.apache.spark:spark-streaming-kafka_2.11:1.6.1,com.datastax.spark:spark-cassandra-connector_2.11:1.6.0-M2 pyspark-shell'

# Define constants for user actions
ACTION_SEARCH = 1
ACTION_FILTER = 2
ACTION_CLICK = 3

# Define the sliding interval
duration = 10

# ___Rdd processing functions___

def get_top10(rdd):
    """Get the top10 searched locations for the last 10 minutes"""
    window_length = 10 * 60  # 10 minutes
    sliding_interval = duration

    # 1- Filter the Seach actions
    # 2- Group by destination and count the ocurrences
    # 3- Sort by count descending
    # 4- Print the top 10
    rdd.filter(lambda x: x.action == ACTION_SEARCH) \
       .map(lambda x: (x.destination, 1)) \
       .reduceByKeyAndWindow(lambda x, y: x + y,
                             lambda x, y: x - y,
                             window_length, sliding_interval) \
       .map(lambda (a, b): (b, a)) \
       .transform(lambda rdd: rdd.sortByKey(ascending=False)) \
       .map(lambda (b, a): {"destination": a, "search_count": b}) \
       .foreachRDD(print_top10)


def print_top10(rdd):
    """Print an array with the 10 first elements of a rdd"""
    print rdd.take(10)


def save_to_cassandra_with_date(rdd):
    """Save the rdd to cassandra adding a column with the date extracted
    from the time field"""

    if not rdd.isEmpty():
        df = click_receiver.sqlContext.createDataFrame(rdd)
        to_pattern = 'yyyy-MM-dd'
        selected_df = df.select(from_unixtime(df.time, to_pattern).alias("date"),
                                df.user_id,
                                df.time,
                                df.hotel)
        selected_df.write \
                   .format("org.apache.spark.sql.cassandra")\
                   .mode('append')\
                   .options(table="userclicksperday", keyspace="clicklog")\
                   .save()


def save_click_stream_to_cassandra(rdd):
    """Filter the click messages and save then in cassandra"""
    rdd.filter(lambda x: x.action == ACTION_CLICK) \
       .foreachRDD(save_to_cassandra_with_date)


# ___Query functions___

def query_second_clicked_hotel_yesterday():
    """Obtain a list with the second hotel clicked yesterday by each user"""
    # Connect to the cassandra database and load the table schema
    df_cass = click_receiver.sqlContext.read \
                            .format("org.apache.spark.sql.cassandra") \
                            .options(table="userclicksperday",
                                     keyspace="clicklog") \
                            .load()

    # Due to the cassandra/spark bug:
    #        https://github.com/holdenk/spark-testing-base/issues/101
    # its not possible to query by the rowkey using equals comparation
    # the solution to query by yesterday is to query by date higher than
    # before yesterday and lower than today

    # 1- Select messages from yesterday
    # 2- Remove the duplicated user/hotel combinations
    # 3- Group by user
    # 4- Take the second item, or null for each user
    before_yesterday_str = str(date.today() - timedelta(2))
    today_str = str(date.today())
    out = df_cass.where((df_cass.date > before_yesterday_str) &
                        (df_cass.date < today_str)) \
                 .select(df_cass.user_id, df_cass.hotel) \
                 .dropDuplicates(['user_id', 'hotel']) \
                 .rdd.map(lambda x: (x.user_id, x.hotel)) \
                 .groupByKey() \
                 .mapValues(lambda x: list(x)[1] if len(list(x)) > 1 else None)
    return out.collect()

if __name__ == "__main__":
    # Start reading the kafka topic
    clickreceiver = ClickReceiver("clicklog", duration)
    clickreceiver.setup([get_top10, save_click_stream_to_cassandra])
    clickreceiver.start()
