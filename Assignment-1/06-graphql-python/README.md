# Exercise 06 — GraphQL (Python)

Python translation of `../06-graphql`. It is deliberately incomplete: the resolvers are the learning exercise.

```bash
python3 -m pip install -r requirements.txt
python3 GraphQLServer.py
```

Open <http://localhost:8086>, or POST GraphQL JSON to `/graphql`.

## Unsolved TODOs

1. `restaurants(cuisine)` — optional, case-insensitive cuisine filter.
2. `restaurant(id)` — a restaurant or `None`.
3. `menu(restaurant_source, vegOnly)` — parent field resolver, including the menu-query counter.
4. `add_review(input)` — validation, persistence, and return value.

`reviews` is implemented as the reference field-resolver pattern. REST comparison endpoints remain at `/rest/restaurants` and `/rest/restaurants/{id}/menu`.
