# Click log streaming using Kafka

## Background
 Assuming that the data is available as messages in a stream in e.g. the form of a Kafka topic "clicklog" with the messages using the following definition/schema:   

 ```cpp
    message ClickLog {      
        optional int64 user_id = 1;      
        optional string time = 2;      
        optional string action = 3;      
        optional string  destination = 4;      
        optional string  hotel = 5;  
    }   
```

Action could be for example "search", "filter" or "click" Destination and Hotel usually contain a unique identifier for the destination (e.g. a city, region or country) resp. the hotel.

## Solution

### Messaging System
For the messaging system I will use Apache Kafka. It is an active open source project (https://github.com/apache/kafka/graphs/contributors), so it's easy to find help in case of questions and bugs can be reported to be fixed by the community. As the project will be dealing with a huge amount of messages, the tool used to stream the data needs to be scalable and fault tolerant. Another requirement for the messaging system is to have a well implemented integration with the system that will process the incoming streams. For the processing layer, I will use spark, than Kafka is a good choice for the message system, since it has a simple and well documented interface built into the Streaming API.

### Serialization
The messages will be serialized using Avro, a schema based data serialization system. The simpler choice would be json, which is human readable and native in most programming languages, but Avro presents a better solution because of it’s schema approach. Having a defined schema simplifies the definition of boundaries between the modules and with avro there is no need to implement format validations and test for fulfillment of required fields.

### Processing Layer
The processing layer used for this project is Apache Spark. As the system requires near real time processing, the Spark solution for streaming using micro batches is a better fit than the Apache Storm and Samza Solution, which are focused in dealing with each event individually. Besides that, Samza is not indicated for counting and aggregation, which is the base of our solution. A good comparison between them can be found at https:// www.mapr.com/blog/stream-processing-everywhere-what-use.
The solution for the problems 4 and 5 were implemented in tree modules:
* The click_producer.py module, generates a Kafka stream of random avro messages to
test the solution.
* The click_receiver.py creates the Spark Context and provides the class ClickReceiver
with the functions to read the stream and execute functions on each stream window.
* The execute_consumer.py when executed, starts the stream reader process. It also
provides the functions to get the top 10 most searched destinations in the last 10 minutes and to get the second distinct hotel the each user clicked on.
* The function get_top10 of the module execute_consumer.py obtains the 10 most searched destinations within the last 10 minutes. It was implemented using a spark streaming window of 10 minutes that updates the calculation every 10 seconds.
* For this problem, considering that the system will handle millions of messages per minute, it’s not possible to use the spark streaming API to accumulate data for 24 hours. For five million users per minute, it will take about 144 GB of memory for a simple calculation that should only run once a day. The best solution is use the streaming API to store the user click data into a NoSql database and query daily for the second hotel clicked by each user.

In the module execute_consumer.py, the function save_to_cassandra_with_date saves the streams to a cassandra table and the function query_second_clicked_hotel_yesterday can be scheduled using a cron job to run daily and return the second distinct hotel clicked by each user on the last day.
