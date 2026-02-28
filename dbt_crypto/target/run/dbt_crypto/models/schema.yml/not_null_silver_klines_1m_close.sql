
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select close
from "crypto_analytics"."public_silver"."silver_klines_1m"
where close is null



  
  
      
    ) dbt_internal_test