
      -- back compat for old kwarg name
  
  
        
            
                
                
            
                
                
            
        
    

    

    merge into "crypto_analytics"."public_silver"."silver_klines_1m" as DBT_INTERNAL_DEST
        using "silver_klines_1m__dbt_tmp164507161430" as DBT_INTERNAL_SOURCE
        on (
                    DBT_INTERNAL_SOURCE.symbol = DBT_INTERNAL_DEST.symbol
                ) and (
                    DBT_INTERNAL_SOURCE.minute_ts = DBT_INTERNAL_DEST.minute_ts
                )

    
    when matched then update set
        "symbol" = DBT_INTERNAL_SOURCE."symbol","minute_ts" = DBT_INTERNAL_SOURCE."minute_ts","open" = DBT_INTERNAL_SOURCE."open","high" = DBT_INTERNAL_SOURCE."high","low" = DBT_INTERNAL_SOURCE."low","close" = DBT_INTERNAL_SOURCE."close","volume" = DBT_INTERNAL_SOURCE."volume","trade_count" = DBT_INTERNAL_SOURCE."trade_count","source_type" = DBT_INTERNAL_SOURCE."source_type","ingested_at" = DBT_INTERNAL_SOURCE."ingested_at","dbt_updated_at" = DBT_INTERNAL_SOURCE."dbt_updated_at"
    

    when not matched then insert
        ("symbol", "minute_ts", "open", "high", "low", "close", "volume", "trade_count", "source_type", "ingested_at", "dbt_updated_at")
    values
        ("symbol", "minute_ts", "open", "high", "low", "close", "volume", "trade_count", "source_type", "ingested_at", "dbt_updated_at")


  