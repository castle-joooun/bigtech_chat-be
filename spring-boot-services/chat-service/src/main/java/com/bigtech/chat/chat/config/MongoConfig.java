package com.bigtech.chat.chat.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.config.EnableMongoAuditing;
import org.springframework.data.mongodb.repository.config.EnableMongoRepositories;

/**
 * MongoDB 설정
 */
@Configuration
@EnableMongoAuditing
@EnableMongoRepositories(basePackages = "com.bigtech.chat.chat.repository")
public class MongoConfig {
}
