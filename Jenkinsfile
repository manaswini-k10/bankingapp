pipeline {
  agent any

  environment {
    REGISTRY = "docker.io"
    IMAGE_NAME = "your-dockerhub-username/bank-app"
    IMAGE_TAG = "latest"
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Build Image') {
      steps {
        sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
      }
    }

    stage('Login & Push') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'dockerhub-creds',
          usernameVariable: 'DOCKER_USER',
          passwordVariable: 'DOCKER_PASS'
        )]) {
          sh '''
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin ${REGISTRY}
            docker push ${IMAGE_NAME}:${IMAGE_TAG}
          '''
        }
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        sh '''
          kubectl apply -f deployment.yaml
          kubectl apply -f service.yaml
          kubectl rollout status deploy/bank-app-deploy
        '''
      }
    }
  }

  post {
    success { echo 'Bank app deployed successfully!' }
    failure { echo 'Build or deployment failed.' }
  }
}
