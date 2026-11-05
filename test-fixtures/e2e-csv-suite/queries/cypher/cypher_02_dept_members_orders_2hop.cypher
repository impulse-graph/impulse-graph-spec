MATCH (d:Department)-[:DEPT_HAS_MEMBER]->(u:User)<-[:ORDER_PLACED_BY]-(o:Order) WHERE d.id = $seed RETURN o
