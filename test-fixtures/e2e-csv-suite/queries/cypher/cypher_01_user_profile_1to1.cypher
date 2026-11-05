MATCH (u:User)-[:USER_HAS_PROFILE]->(p:Profile) WHERE u.id = $seed RETURN p
