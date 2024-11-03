provider "aws" {
  region = "us-east-1" # Update to your preferred region
}

resource "aws_key_pair" "deployer_key" {
  key_name   = "deployer_key"
  public_key = file("~/.ssh/id_rsa.pub") 
}

resource "aws_security_group" "allow_ssh_http" {
  name        = "allow_ssh_http"
  description = "Allow SSH and HTTP access"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "docker_host" {
  ami           = "ami-0c55b159cbfafe1f0" # Amazon Linux 2 AMI (update to the latest)
  instance_type = "t2.micro" # Update as per your need
  key_name      = aws_key_pair.deployer_key.key_name
  security_groups = [aws_security_group.allow_ssh_http.name]

  user_data = <<-EOF
              #!/bin/bash
              yum update -y
              amazon-linux-extras install docker -y
              service docker start
              usermod -a -G docker ec2-user
              docker run -d -p 80:80 YOUR_DOCKER_IMAGE # Replace with your Docker image
              EOF

  tags = {
    Name = "Docker-Host"
  }
}

output "instance_ip" {
  value = aws_instance.docker_host.public_ip
  description = "The public IP of the EC2 instance running Docker."
}
