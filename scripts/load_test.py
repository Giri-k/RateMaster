from locust import HttpUser, task, between, events

denied = {"search": 0, "status": 0, "login": 0}
total = {"search": 0, "status": 0, "login": 0}


class RateMasterUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(7)
    def search(self):
        resp = self.client.get("/api/search")
        total["search"] += 1
        if resp.status_code == 429:
            denied["search"] += 1

    @task(2)
    def status(self):
        resp = self.client.get("/api/status")
        total["status"] += 1
        if resp.status_code == 429:
            denied["status"] += 1

    @task(1)
    def login(self):
        resp = self.client.post("/api/login")
        total["login"] += 1
        if resp.status_code == 429:
            denied["login"] += 1


@events.quitting.add_listener
def print_summary(**kwargs):
    print("\n" + "=" * 60)
    print("RATE LIMIT SUMMARY")
    print("=" * 60)
    for endpoint in ["search", "status", "login"]:
        t = total[endpoint]
        d = denied[endpoint]
        rate = (d / t * 100) if t > 0 else 0
        print(f"  /api/{endpoint:8s}  total={t:5d}  denied={d:5d}  deny_rate={rate:.1f}%")
    print("=" * 60)
