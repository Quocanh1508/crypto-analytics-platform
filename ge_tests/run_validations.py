import os
import sys
import logging
from dotenv import load_dotenv
import great_expectations as gx
from great_expectations.core.batch import BatchRequest
from great_expectations.exceptions import DataContextError

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

PG_HOST = os.getenv('POSTGRES_HOST', 'postgres')
if "postgres" in PG_HOST and not os.environ.get("RUNNING_IN_DOCKER"):
    PG_HOST = "localhost"
PG_PORT = os.getenv('POSTGRES_PORT', '5432')
PG_USER = os.getenv('POSTGRES_USER', 'postgres')
PG_PASS = os.getenv('POSTGRES_PASSWORD', 'postgres')
PG_DB = os.getenv('POSTGRES_ANALYTICS_DB', 'crypto_analytics')

def setup_ge():
    # Initialize GE Context in memory (or file if needed)
    context_root_dir = os.path.join(os.path.dirname(__file__), "great_expectations")
    
    try:
        context = gx.get_context(context_root_dir=context_root_dir)
        logger.info("Found existing GE context.")
    except DataContextError:
        logger.info("Initializing new GE context...")
        # A simpler approach for script-based GE is to let the CLI scaffold it, 
        # but since we want to be programmatic:
        os.system(f"cd {os.path.dirname(__file__)} && yes | great_expectations init")
        context = gx.get_context(context_root_dir=context_root_dir)

    datasource_name = "crypto_postgres"
    
    # 1. Configure Datasource
    connection_string = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    
    datasource_config = {
        "name": datasource_name,
        "class_name": "Datasource",
        "execution_engine": {
            "class_name": "SqlAlchemyExecutionEngine",
            "connection_string": connection_string,
        },
        "data_connectors": {
            "default_configured_data_connector_name": {
                "class_name": "ConfiguredAssetSqlDataConnector",
                "assets": {
                    "silver_klines_1m": {
                        "schema_name": "public_silver",
                        "table_name": "silver_klines_1m"
                    }
                }
            },
        },
    }
    
    context.test_yaml_config(yaml_config=str(datasource_config))
    context.add_datasource(**datasource_config)
    logger.info("Configured Postgres datasource.")

    # 2. Create an Expectation Suite for the Silver Layer
    suite_name = "silver_klines_suite"
    context.add_expectation_suite(expectation_suite_name=suite_name)
    logger.info(f"Created suite {suite_name}")

    # 3. Add Expectations
    batch_request = BatchRequest(
        datasource_name=datasource_name,
        data_connector_name="default_configured_data_connector_name",
        data_asset_name="silver_klines_1m",
    )
    
    validator = context.get_validator(
        batch_request=batch_request, expectation_suite_name=suite_name
    )

    logger.info("Adding expectations to silver_klines_1m...")
    
    # Assertions on Silver layer
    validator.expect_table_columns_to_match_ordered_list(
        column_list=["symbol", "minute_ts", "open", "high", "low", "close", "volume", "trade_count", "source_type", "ingested_at", "dbt_updated_at"]
    )
    validator.expect_column_values_to_not_be_null(column="symbol")
    validator.expect_column_values_to_not_be_null(column="minute_ts")
    validator.expect_column_values_to_be_in_set(column="symbol", value_set=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    
    validator.expect_column_values_to_not_be_null(column="high")
    validator.expect_column_values_to_not_be_null(column="low")
    
    # Volume should be positive
    validator.expect_column_values_to_be_between(
        column="volume", min_value=0.0
    )

    validator.save_expectation_suite(discard_failed_expectations=False)
    logger.info("Saved expectations.")

    # 4. Run Validation
    logger.info("Running validation on Silver layer...")
    checkpoint_name = "silver_klines_checkpoint"
    
    checkpoint_config = {
        "name": checkpoint_name,
        "config_version": 1.0,
        "class_name": "SimpleCheckpoint",
        "run_name_template": "%Y%m%d-%H%M%S-crypto-validation",
        "validations": [
            {
                "batch_request": batch_request,
                "expectation_suite_name": suite_name
            }
        ]
    }
    context.add_checkpoint(**checkpoint_config)
    results = context.run_checkpoint(checkpoint_name=checkpoint_name)
    
    if results["success"]:
        logger.info("✅ Great Expectations Validation PASSED!")
    else:
        logger.error("❌ Great Expectations Validation FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    setup_ge()
