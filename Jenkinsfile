#!/usr/bin/groovy
// 2017-07-22 Note: preferred way for Jenkinsfile is "Declarative syntax". However there are not many examples yet, and not yet available with docker (needs escaping to scripts)
// After example of: https://github.com/lachie83/croc-hunter/blob/master/Jenkinsfile

podTemplate(label: 'jenkins-pipeline', containers: [
	containerTemplate(name: 'jnlp',
	                  image: "gcr.io/${env.GKE_PROJECT}/jnlp:latest",
					  args: '${computer.jnlpmac} ${computer.name}',
            command: '',
					  workingDir: '/home/jenkins',
					  resourceRequestCpu: '200m',
					  resourceLimitCpu: '200m',
					  resourceRequestMemory: '256Mi',
					  resourceLimitMemory: '256Mi'),
  ],
  volumes: [
	  hostPathVolume(mountPath: '/usr/bin/docker', hostPath: '/usr/bin/docker'),
	  hostPathVolume(mountPath: '/var/run/docker.sock', hostPath: '/var/run/docker.sock'),
  ]
)
	
{
  node ('jenkins-pipeline') {

	checkout scm

    // Configure environment variables
	env.GIT_SHA = sh(returnStdout: true, script: 'git rev-parse HEAD').trim().substring(0, 7)
    env.APP_NAME = env.JOB_NAME.split("/")[0]
    env.CHART_DIR = pwd() + "/chart/${env.APP_NAME}"
    env.IMAGE_REPOSITORY = "gcr.io/${env.GKE_PROJECT}/${env.APP_NAME}"
    env.IMAGE_TAG = "${env.BRANCH_NAME}.${env.GIT_SHA}"

    stage ('Build container') {    
      container('jnlp') {
        sh("docker build -t ${env.IMAGE_REPOSITORY}:${env.IMAGE_TAG} .")
      }
    }

    // Testing stage should go here
    
    stage ('Test Helm') {
      container('jnlp') {
        // run helm chart linter
        sh "helm lint ${env.CHART_DIR}"

        // run dry-run helm chart installation
        sh "helm upgrade --dry-run --install ${env.APP_NAME} ${env.CHART_DIR} --set image.tag=${env.IMAGE_TAG},image.repository=${env.IMAGE_REPOSITORY} --namespace=dev"
      }
    }
    
    stage ('Push to registry') {    
      container('jnlp') {
        sh("gcloud docker -- push ${env.IMAGE_REPOSITORY}:${env.IMAGE_TAG}")
      }
    }    
    
    // Deploy
    stage ('Deploy helm chart') {
      container('jnlp') {
        switch (env.BRANCH_NAME) {
          case "develop":
            sh "helm upgrade --install dev-${env.APP_NAME} ${env.CHART_DIR} --set image.tag=${env.IMAGE_TAG},image.repository=${env.IMAGE_REPOSITORY} --namespace=dev"
            break
          case "master":
            sh "helm upgrade --install prd-${env.APP_NAME} ${env.CHART_DIR} --set image.tag=${env.IMAGE_TAG},image.repository=${env.IMAGE_REPOSITORY} --namespace=prd"
            break
          default:
            println("Unknown branch, not deploying anything")            
        }
      }
    }
  }
}