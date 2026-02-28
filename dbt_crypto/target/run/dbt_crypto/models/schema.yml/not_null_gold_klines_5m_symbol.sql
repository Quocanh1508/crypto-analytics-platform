
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select symbol
from "crypto_analytics"."public_gold"."gold_klines_5m"
where symbol is null



  
  
      
    ) dbt_internal_test