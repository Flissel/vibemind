#!/usr/bin/env bash
set -e

MONGO=$(docker ps -qf name=rowboat-mongo)
ROWBOAT=$(docker ps -qf name=vibemind_rowboat.1)

echo "mongo: $MONGO"
echo "rowboat: $ROWBOAT"
echo ""

echo "=== List databases ==="
docker exec "$MONGO" mongosh --quiet --eval 'show dbs' 2>&1

echo ""
echo "=== rowboat DB collections ==="
docker exec "$MONGO" mongosh rowboat --quiet --eval 'db.getCollectionNames().forEach(c => print("  " + c + ":  " + db.getCollection(c).countDocuments() + " docs"))' 2>&1

echo ""
echo "=== Sample doc from each collection (1 doc) ==="
docker exec "$MONGO" mongosh rowboat --quiet --eval '
  db.getCollectionNames().forEach(function(c) {
    print("");
    print("---- " + c + " ----");
    var sample = db.getCollection(c).findOne();
    if (sample) {
      print(JSON.stringify(sample, null, 2).substring(0, 800));
    } else {
      print("(empty)");
    }
  })' 2>&1
