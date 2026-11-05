MATCH (g:Group)-[:GROUP_INCLUDES*]->(sub:Group) WHERE g.id = $seed RETURN sub
