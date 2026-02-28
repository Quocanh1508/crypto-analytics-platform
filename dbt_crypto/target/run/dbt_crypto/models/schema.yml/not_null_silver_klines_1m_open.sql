
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select open
from "crypto_analytics"."public_silver"."silver_klines_1m"
where open is null



  
  
      
    ) dbt_internal_test