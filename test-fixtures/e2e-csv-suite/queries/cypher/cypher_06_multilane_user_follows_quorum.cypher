MATCH (u:User)-[:USER_FOLLOWS]->(f:User) WHERE u.id IN [0, 1, 2] AND f.quorum = 2 RETURN f
