
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select minute_ts
from "crypto_analytics"."public_silver"."silver_klines_1m"
where minute_ts is null



  
  
      
    ) dbt_internal_test