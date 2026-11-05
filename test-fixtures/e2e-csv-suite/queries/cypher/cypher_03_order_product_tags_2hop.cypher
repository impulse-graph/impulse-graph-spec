MATCH (o:Order)-[:ORDER_CONTAINS_PRODUCT]->(p:Product)-[:PRODUCT_HAS_TAG]->(t:Tag) WHERE o.id = $seed RETURN t
