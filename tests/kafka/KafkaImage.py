import docker
from time import sleep
import os
from confluent_kafka.admin import AdminClient


class KafkaImage:
    def __init__(self):
        self.image = "spotify/kafka"
        self.name = "kafka"
        self.host = "localhost"
        self.port = 9092

    def get_image_options(self):
        image_options = {
            "version": "latest",
            "environment": {
                "ADVERTISED_PORT": "9092",
                "ADVERTISED_HOST": "0.0.0.0",
            },
            "ports": {"9092": "9092", "2181": "2181"},
        }

        return image_options

    def check(self):
        client = AdminClient({"bootstrap.servers": "localhost:9092"})
        try:
            client.list_topics(timeout=10)
            return True
        except Exception as excep:
            print(excep)
            return False

    # This is based on the 'pytest_docker_fixtures' library
    def run(self):
        docker_client = docker.from_env()
        image_options = self.get_image_options()

        max_wait_s = image_options.pop("max_wait_s", None) or 30

        # Create a new one
        container = docker_client.containers.run(
            image=self.image, **image_options, detach=True
        )
        ident = container.id
        count = 1

        self.container_obj = docker_client.containers.get(ident)

        opened = False

        print(f"starting {self.name}")
        while count < max_wait_s and not opened:
            if count > 0:
                sleep(1)
            count += 1
            try:
                self.container_obj = docker_client.containers.get(ident)
            except docker.errors.NotFound:
                print(f"Container not found for {self.name}")
                continue
            if self.container_obj.status == "exited":
                logs = self.container_obj.logs()
                self.stop()
                raise Exception(f"Container failed to start {logs}")

            if self.container_obj.attrs["NetworkSettings"]["IPAddress"] != "":
                if os.environ.get("TESTING", "") == "jenkins":
                    network = self.container_obj.attrs["NetworkSettings"]
                    self.host = network["IPAddress"]
                else:
                    self.host = "localhost"

            if self.host != "":
                opened = self.check()
        if not opened:
            logs = self.container_obj.logs().decode("utf-8")
            self.stop()
            raise Exception(
                f"Could not start {self.name}: {logs}\n"
                f"Image: {self.image}\n"
                f"Options:\n{(image_options)}"
            )
        print(f"{self.name} started")
        return self.host, self.port

    def stop(self):
        if self.container_obj is not None:
            try:
                self.container_obj.kill()
            except docker.errors.APIError:
                pass
            try:
                self.container_obj.remove(v=True, force=True)
            except docker.errors.APIError:
                pass
