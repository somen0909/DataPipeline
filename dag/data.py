from datetime import datetime, timedelta
import requests
import psycopg2
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.amazon.aws.sensors.s3_key import S3KeySensor
from airflow.hooks.postgres_hook import PostgresHook

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 5, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def fetch_covid_data(country_code):
    api_url = f'https://health.google.com/covid-19/open-data/{country_code}'
    response = requests.get(api_url)
    data = response.json()
    return data

def clean_data(data):
    # Perform data cleansing tasks here
    cleaned_data = data  # Placeholder, actual cleaning steps depend on data structure
    return cleaned_data

def aggregate_data(cleaned_data):
    # Perform data aggregation tasks here
    aggregated_data = cleaned_data  # Placeholder, actual aggregation depends on data structure
    return aggregated_data

def store_in_postgres(aggregated_data):
    pg_hook = PostgresHook(postgres_conn_id='postgres_conn_id')
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    
    # Create table if not exists
    create_table_query = """
    CREATE TABLE IF NOT EXISTS covid_data (
        state VARCHAR(100),
        district VARCHAR(100),
        block VARCHAR(100),
        cases INT,
        deaths INT,
        recoveries INT
    )
    """
    cursor.execute(create_table_query)
    
    # Insert data into table
    insert_query = """
    INSERT INTO covid_data (state, district, block, cases, deaths, recoveries)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    for row in aggregated_data:
        cursor.execute(insert_query, row)
    
    connection.commit()
    cursor.close()
    connection.close()

with DAG('covid_data_pipeline',
         default_args=default_args,
         schedule_interval=None,  # Disable automatic scheduling
         catchup=False) as dag:

    s3_sensor = S3KeySensor(
        task_id='s3_sensor',
        bucket_key='s3://your-bucket/your-folder/',
        wildcard_match=True,
        timeout=300,  # Timeout after 5 minutes if file not found
        poke_interval=30,  # Check every 30 seconds
    )

    fetch_data = PythonOperator(
        task_id='fetch_covid_data',
        python_callable=fetch_covid_data,
        op_kwargs={'country_code': '{{ ti.xcom_pull(task_ids="s3_sensor") }}'},
        provide_context=True
    )

    clean_data = PythonOperator(
        task_id='clean_data',
        python_callable=clean_data,
        provide_context=True
    )

    aggregate_data = PythonOperator(
        task_id='aggregate_data',
        python_callable=aggregate_data,
        provide_context=True
    )

    store_in_postgres = PythonOperator(
        task_id='store_in_postgres',
        python_callable=store_in_postgres,
        provide_context=True
    )

    s3_sensor >> fetch_data >> clean_data >> aggregate_data >> store_in_postgres
