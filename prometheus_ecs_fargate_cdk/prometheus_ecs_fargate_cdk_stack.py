from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecs_patterns as ecsp,
    aws_secretsmanager as sm,
    aws_servicediscovery as cloudmap,
    App, Stack
)

from constructs import Construct

class PrometheusEcsFargateCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        PREFIX      = 'prom-ecs-fargate-'
        APP_PATH    = '/prometheus'
        VOLUME_NAME = 'cdk-ecs-prom-efs-volume'

        # The code that defines your stack goes here
        vpc = ec2.Vpc(
            self, PREFIX + 'Vpc',
            max_azs=3
        )

        cluster = ecs.Cluster(
            self, PREFIX + 'Cluster',
            vpc=vpc,
        )

        # Create an Amazon Elastic File System (EFS), with the logical ID CDK-efs-sample-EFS
        file_system = efs.FileSystem(
            self, PREFIX + 'EFS',
            vpc=vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
        )

        # Create an Access Point for the EFS, with the logical ID CDK-efs-sample-AccessPoint
        access_point = efs.AccessPoint(
            self, PREFIX + 'AccessPoint',
            file_system=file_system,
            path='/prometheus',
            create_acl=efs.Acl(
                owner_uid="65534",
                owner_gid="65534",
                permissions="777"
            ),
            posix_user=efs.PosixUser(
                uid="65534",
                gid="65534"
            )
        )

        # Create a new EFS volume configuration for the ECS Task
        efs_volume_configuration = ecs.EfsVolumeConfiguration(
            file_system_id=file_system.file_system_id,

            # The logical ID of the Access Point to use.
            # This is a string, not an ARN.
            authorization_config=ecs.AuthorizationConfig(
                access_point_id=access_point.access_point_id,
                iam='ENABLED',
            ),
            transit_encryption='ENABLED',
        )

        # Create a new IAM Role for the ECS Task
        task_role = iam.Role (
            self, PREFIX + 'EcsTaskRole',
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com').with_conditions({
                "StringEquals": {
                    "aws:SourceAccount": Stack.of(self).account
                },
                "ArnLike":{
                    "aws:SourceArn":"arn:aws:ecs:" + Stack.of(self).region + ":" + Stack.of(self).account + ":*"
                },
            }),
        )

        # Attach a managed policy to the IAM Role
        task_role.attach_inline_policy(
            iam.Policy(self, PREFIX +'Policy',
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        resources=['*'],
                        actions=[
                            "ecr:GetAuthorizationToken",
                            "ec2:DescribeAvailabilityZones"
                        ]
                    ),
                    iam.PolicyStatement(
                        sid='AllowEfsAccess',
                        effect=iam.Effect.ALLOW,
                        resources=['*'],
                        actions=[
                            'elasticfilesystem:ClientRootAccess',
                            'elasticfilesystem:ClientWrite',
                            'elasticfilesystem:ClientMount',
                            'elasticfilesystem:DescribeMountTargets'
                        ]
                    )
                ]
            )
        )

        # Add a new container to the Fargate Task Definition
        mount_point = ecs.MountPoint(
            container_path=APP_PATH,
            source_volume=VOLUME_NAME,
            read_only=False,
        )

        # Add a new port mapping to the Fargate Task Definition
        port_mapping = ecs.PortMapping(
            container_port=9090,
            host_port=9090,
            protocol=ecs.Protocol.TCP,
        )
        port_mapping2 = ecs.PortMapping(
            container_port=3000,
            host_port=3000,
            protocol=ecs.Protocol.TCP,
        )

        task_definition = ecs.FargateTaskDefinition(self, "TaskDef", task_role=task_role)

        # Add a new volume to the Fargate Task Definition
        task_definition.add_volume(
            name=VOLUME_NAME,
            efs_volume_configuration=efs_volume_configuration,
        )

        task_definition.add_volume(
            name="myvol",
            host=None,
        )
        task_definition.add_volume(
            name="myvol2",
            host=None,
        )

        secret = sm.Secret.from_secret_complete_arn(self,id='App4PCC',secret_complete_arn='arn:aws:secretsmanager:ap-southeast-2:010438472260:secret:App4PCC-xOLOCY')
        
        # Add Init Container
        initContainer = task_definition.add_container(
            id="initContainer",
            image=ecs.ContainerImage.from_registry('docker.io/library/alpine'),
            entry_point=['/bin/ash', '-c', 'echo "$PROM_CONFIG" | base64 -d | tee /etc/prometheus/prometheus.yml && printenv SECRET_ID > /etc/prometheus/secret_id && printenv SECRET_KEY > /etc/prometheus/secret_key'],
            essential=False,
            secrets={
                "SECRET_ID": ecs.Secret.from_secrets_manager(secret,'secret_id'),
                "SECRET_KEY": ecs.Secret.from_secrets_manager(secret,'secret_key')
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix='cdk-ecs-prometheus', 
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
        )

        mount_point2=ecs.MountPoint(container_path='/etc/prometheus',read_only=False,source_volume='myvol')
        initContainer.add_mount_points(mount_point2)

        initContainer.add_environment(
            name="PROM_CONFIG",
            value="Z2xvYmFsOgogIHNjcmFwZV9pbnRlcnZhbDogMTVzCiAgc2NyYXBlX3RpbWVvdXQ6IDEwcwogIGV2YWx1YXRpb25faW50ZXJ2YWw6IDE1cwpzY3JhcGVfY29uZmlnczoKICAjIFByaXNtYSBDbG91ZCBzY3JhcGUgY29uZmlndXJhdGlvbgogIC0gam9iX25hbWU6IHR3aXN0bG9jawogICAgc2NoZW1lOiBodHRwcwogICAgc3RhdGljX2NvbmZpZ3M6CiAgICAgICMgUmVwbGFjZSAidGFyZ2V0IiBhbmQgIm1ldHJpY3NfcGF0aCIgd2l0aCB5b3VyIHBhdGggdG8gQ29uc29sZSByZXNwZWN0aXZlbHkKICAgICAgLSB0YXJnZXRzOiBbInVzLXdlc3QxLmNsb3VkLnR3aXN0bG9jay5jb20iXQogICAgbWV0cmljc19wYXRoOiAvdXMtNC0xNjEwNTUyODMvYXBpL3YxL21ldHJpY3MKICAgICMgQWNjZXNzL3NlY3JldCBBUEkga2V5IHdpdGggQ29tcHV0ZSBBdWRpdG9yIChvciBncmVhdGVyKSBhY2Nlc3MKICAgIGJhc2ljX2F1dGg6CiAgICAgIHVzZXJuYW1lX2ZpbGU6ICIvZXRjL3Byb21ldGhldXMvc2VjcmV0X2lkIgogICAgICBwYXNzd29yZF9maWxlOiAiL2V0Yy9wcm9tZXRoZXVzL3NlY3JldF9rZXkiCgo=="
        )

        initContDep = ecs.ContainerDependency(
            container=initContainer,
            condition=ecs.ContainerDependencyCondition.SUCCESS
        )

        # Add a new container to the Fargate Task Definition
        container = ecs.ContainerDefinition(
            self, 'prometheus',
            task_definition=task_definition,
            image=ecs.ContainerImage.from_registry('docker.io/prom/prometheus'),
            user='nobody',
            # command=['--config.file=/etc/prometheus/prometheus.yml', '--storage.tsdb.path=/data/prometheus', '--log.level=debug'],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix='cdk-ecs-prometheus', 
                log_retention=logs.RetentionDays.ONE_MONTH,
            )
        )

        # Wait for init Container to finish
        container.add_container_dependencies(initContDep)

        # Add a new volume to the Fargate Task Definition
        container.add_mount_points(mount_point),
        container.add_mount_points(mount_point2)

        # Add a new port mapping to the Fargate Task Definition
        container.add_port_mappings(port_mapping),

        # Add a new container to the Fargate Task Definition
        container2 = ecs.ContainerDefinition(
            self, 'grafana',
            task_definition=task_definition,
            image=ecs.ContainerImage.from_registry('docker.io/grafana/grafana'),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix='cdk-ecs-prometheus', 
                log_retention=logs.RetentionDays.ONE_MONTH,
            )
        )

        # Wait for init Container to finish
        container2.add_container_dependencies(initContDep)

        # Add a new port mapping to the Fargate Task Definition
        container2.add_port_mappings(port_mapping2),

        # namespace = cloudmap.PrivateDnsNamespace(self, PREFIX + 'Namespace',
        #     name='local',
        #     vpc=vpc
        # )

        fargate_service = ecs.FargateService(self, "FargateService",
            cluster=cluster,
            task_definition=task_definition,
            min_healthy_percent=100,
            # assign_public_ip=True,
            capacity_provider_strategies=[ecs.CapacityProviderStrategy(
                capacity_provider="FARGATE_SPOT",
                weight=2
            ), ecs.CapacityProviderStrategy(
                capacity_provider="FARGATE",
                weight=1
            )
            ],
            # cloud_map_options=ecs.CloudMapOptions(
            #     # Create A records - useful for AWSVPC network mode.
            #     # dns_record_type=cloudmap.DnsRecordType.A,
            #     cloud_map_namespace=namespace,
            #     container=container2,
            #     container_port=3000,
            # )
        )

        # Allow the ECS Service to connect to the EFS
        fargate_service.connections.allow_from(file_system, ec2.Port.tcp(2049)),

        # Allow the EFS to connect to the ECS Service
        fargate_service.connections.allow_to(file_system, ec2.Port.tcp(2049)),

        # Allow connection to Prometheus from any
        fargate_service.connections.allow_from_any_ipv4(ec2.Port.tcp(9090))

        # Allow connection to Grafana from any
        fargate_service.connections.allow_from_any_ipv4(ec2.Port.tcp(3000))