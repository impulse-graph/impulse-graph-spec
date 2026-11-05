MATCH (u:User)-[:USER_FOLLOWS]-(peer:User) WHERE u.id = $seed RETURN count(peer)
