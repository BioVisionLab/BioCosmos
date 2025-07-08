class LepTraitService:
    def __init__(self, db_client):
        self.db_client = db_client

    def get_traits(self):
        query = "SELECT * FROM lep_traits_consensus"
        return self.db_client.execute(query).fetchall()
