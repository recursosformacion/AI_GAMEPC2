/*M!999999\- enable the sandbox mode */ 
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_actuacion_groups` (
  `actuacion_id` char(32) NOT NULL,
  `group_id` char(32) NOT NULL,
  `role` varchar(16) NOT NULL DEFAULT 'participant',
  PRIMARY KEY (`actuacion_id`,`group_id`),
  KEY `idx_amigos_ag_group` (`group_id`),
  CONSTRAINT `fk_amigos_ag_actuacion` FOREIGN KEY (`actuacion_id`) REFERENCES `amigos_actuaciones` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_amigos_ag_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_actuaciones` (
  `id` char(32) NOT NULL,
  `slug` varchar(200) NOT NULL,
  `title` varchar(512) NOT NULL,
  `summary` text DEFAULT NULL,
  `description` longtext DEFAULT NULL,
  `image_url` varchar(1024) DEFAULT NULL,
  `kind` varchar(32) NOT NULL DEFAULT 'concert',
  `modality` varchar(16) NOT NULL DEFAULT 'onsite',
  `event_status` varchar(16) NOT NULL DEFAULT 'scheduled',
  `editorial_status` varchar(16) NOT NULL DEFAULT 'draft',
  `starts_on` date NOT NULL,
  `starts_at` time DEFAULT NULL,
  `ends_on` date DEFAULT NULL,
  `ends_at` time DEFAULT NULL,
  `timezone` varchar(64) DEFAULT NULL,
  `registration_deadline` date DEFAULT NULL,
  `venue_name` varchar(255) DEFAULT NULL,
  `venue_address` varchar(512) DEFAULT NULL,
  `locality` varchar(160) DEFAULT NULL,
  `region` varchar(160) DEFAULT NULL,
  `country_code` char(2) DEFAULT NULL,
  `latitude` decimal(9,6) DEFAULT NULL,
  `longitude` decimal(9,6) DEFAULT NULL,
  `map_url` varchar(1024) DEFAULT NULL,
  `organizer_name` varchar(255) DEFAULT NULL,
  `organizer_website` varchar(1024) DEFAULT NULL,
  `event_url` varchar(1024) DEFAULT NULL,
  `tickets_url` varchar(1024) DEFAULT NULL,
  `price` varchar(120) DEFAULT NULL,
  `access_info` text DEFAULT NULL,
  `public_contact` varchar(254) DEFAULT NULL,
  `organizer_group_id` char(32) DEFAULT NULL,
  `author_user_id` char(36) NOT NULL,
  `last_verified_on` date DEFAULT NULL,
  `internal_notes` text DEFAULT NULL,
  `published_at` datetime(6) DEFAULT NULL,
  `reviewed_by` char(36) DEFAULT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `review_note` varchar(512) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `weight` tinyint(4) NOT NULL DEFAULT 5,
  `views` int(10) unsigned NOT NULL DEFAULT 0,
  `expands` int(10) unsigned NOT NULL DEFAULT 0,
  `buys` int(10) unsigned NOT NULL DEFAULT 0,
  `source_email` varchar(254) DEFAULT NULL,
  `source_note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_amigos_actuacion_slug` (`slug`),
  KEY `idx_amigos_actuacion_date` (`starts_on`),
  KEY `idx_amigos_actuacion_status` (`editorial_status`),
  KEY `fk_amigos_actuacion_org` (`organizer_group_id`),
  CONSTRAINT `fk_amigos_actuacion_org` FOREIGN KEY (`organizer_group_id`) REFERENCES `amigos_groups` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_articles` (
  `id` char(32) NOT NULL,
  `group_id` char(32) DEFAULT NULL,
  `title` varchar(512) NOT NULL,
  `slug` varchar(200) NOT NULL,
  `event_date` date NOT NULL,
  `summary` text DEFAULT NULL,
  `body` longtext DEFAULT NULL,
  `cover_url` varchar(1024) DEFAULT NULL,
  `author_user_id` char(36) NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'draft',
  `published_at` datetime(6) DEFAULT NULL,
  `reviewed_by` char(36) DEFAULT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `review_note` varchar(512) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `scope` varchar(16) NOT NULL DEFAULT 'group',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_amigos_article_slug` (`group_id`,`slug`),
  KEY `idx_amigos_article_status` (`status`),
  KEY `idx_amigos_article_author` (`author_user_id`),
  KEY `idx_amigos_article_event` (`group_id`,`event_date`),
  CONSTRAINT `fk_amigos_article_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_authorizations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` char(36) NOT NULL,
  `scope` varchar(32) NOT NULL,
  `direct_publish` tinyint(1) NOT NULL DEFAULT 0,
  `granted_by` char(36) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_amigos_auth` (`scope`,`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_coral_attributes` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `group_id` char(32) NOT NULL,
  `facet` varchar(32) NOT NULL COMMENT 'repertoire|language',
  `value` varchar(120) NOT NULL,
  `position` int(11) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_amigos_coral_attr` (`group_id`,`facet`,`value`),
  KEY `idx_amigos_coral_attr` (`group_id`,`facet`,`position`),
  CONSTRAINT `fk_amigos_coral_attr_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_coral_details` (`group_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_coral_details` (
  `group_id` char(32) NOT NULL,
  `foundation_date` date DEFAULT NULL,
  `dissolution_date` date DEFAULT NULL,
  `locality` varchar(160) DEFAULT NULL,
  `region` varchar(160) DEFAULT NULL,
  `country_code` char(2) DEFAULT NULL,
  `venue` varchar(255) DEFAULT NULL,
  `formation_type` varchar(48) DEFAULT NULL,
  `member_count` int(11) DEFAULT NULL,
  `website` varchar(1024) DEFAULT NULL,
  `public_email` varchar(254) DEFAULT NULL,
  `director_person_id` varchar(64) DEFAULT NULL,
  `director_label` varchar(255) DEFAULT NULL,
  `linked_entity` varchar(255) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  PRIMARY KEY (`group_id`),
  CONSTRAINT `fk_amigos_coral_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_events` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `group_id` char(32) DEFAULT NULL,
  `article_id` char(32) DEFAULT NULL,
  `event_type` varchar(48) NOT NULL,
  `actor` char(36) DEFAULT NULL,
  `from_status` varchar(16) DEFAULT NULL,
  `to_status` varchar(16) DEFAULT NULL,
  `detail_json` longtext DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_amigos_event_group` (`group_id`,`created_at`),
  KEY `idx_amigos_event_article` (`article_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=55 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_group_catalog` (
  `id` char(32) NOT NULL,
  `group_id` char(32) NOT NULL,
  `scope` varchar(16) NOT NULL,
  `code` varchar(64) NOT NULL,
  `name` varchar(120) NOT NULL,
  `parent_id` char(32) DEFAULT NULL,
  `sort_order` int(11) NOT NULL DEFAULT 0,
  `active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `idx_amigos_catalog_group` (`group_id`,`scope`,`sort_order`),
  CONSTRAINT `fk_amigos_catalog_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_group_history` (
  `id` char(32) NOT NULL,
  `group_id` char(32) NOT NULL,
  `event_type` varchar(32) NOT NULL,
  `member_user_id` char(36) DEFAULT NULL,
  `person_name` varchar(255) DEFAULT NULL,
  `role` varchar(16) DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_amigos_history_group` (`group_id`,`start_date`),
  CONSTRAINT `fk_amigos_history_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_group_links` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `group_id` char(32) NOT NULL,
  `kind` varchar(32) NOT NULL COMMENT 'facebook|instagram|other',
  `label` varchar(64) DEFAULT NULL,
  `url` varchar(1024) NOT NULL,
  `position` int(11) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_amigos_group_link` (`group_id`,`position`),
  CONSTRAINT `fk_amigos_group_link_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_group_types` (
  `code` varchar(64) NOT NULL,
  `parent_code` varchar(64) DEFAULT NULL,
  `name` varchar(160) NOT NULL,
  `kind` varchar(32) NOT NULL,
  `sort_order` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_groups` (
  `id` char(32) NOT NULL,
  `slug` varchar(96) NOT NULL,
  `name` varchar(255) NOT NULL,
  `kind` varchar(32) NOT NULL DEFAULT 'coral',
  `description` text DEFAULT NULL,
  `image_url` varchar(1024) DEFAULT NULL,
  `website` varchar(1024) DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `logo_url` varchar(1024) DEFAULT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'active',
  `editorial_mode` varchar(16) NOT NULL DEFAULT 'moderated',
  `created_by` char(36) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `technical_description` text DEFAULT NULL,
  `admin_roles_json` text DEFAULT NULL,
  `musical_roles_json` text DEFAULT NULL,
  `join_code` varchar(16) DEFAULT NULL,
  `join_code_expires_at` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_amigos_group_slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_media` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `article_id` char(32) NOT NULL,
  `kind` varchar(16) NOT NULL,
  `url` varchar(1024) NOT NULL,
  `provider` varchar(32) DEFAULT NULL,
  `video_id` varchar(64) DEFAULT NULL,
  `caption` varchar(512) DEFAULT NULL,
  `credit` varchar(512) DEFAULT NULL,
  `position` int(11) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_amigos_media_article` (`article_id`,`position`),
  CONSTRAINT `fk_amigos_media_article` FOREIGN KEY (`article_id`) REFERENCES `amigos_articles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_members` (
  `group_id` char(32) NOT NULL,
  `user_id` char(36) NOT NULL,
  `role` varchar(16) NOT NULL DEFAULT 'collaborator',
  `status` varchar(16) NOT NULL DEFAULT 'active',
  `granted_by` char(36) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `admin_role_id` char(32) DEFAULT NULL,
  `musical_role_id` char(32) DEFAULT NULL,
  `section_id` char(32) DEFAULT NULL,
  PRIMARY KEY (`group_id`,`user_id`),
  KEY `idx_amigos_member_user` (`user_id`),
  CONSTRAINT `fk_amigos_member_group` FOREIGN KEY (`group_id`) REFERENCES `amigos_groups` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_role_templates` (
  `id` char(32) NOT NULL,
  `type_code` varchar(64) NOT NULL,
  `scope` varchar(16) NOT NULL,
  `code` varchar(64) NOT NULL,
  `name` varchar(160) NOT NULL,
  `sort_order` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_section_templates` (
  `id` char(32) NOT NULL,
  `type_code` varchar(64) NOT NULL,
  `code` varchar(64) NOT NULL,
  `name` varchar(160) NOT NULL,
  `sort_order` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `amigos_uploads` (
  `file_id` bigint(20) unsigned NOT NULL,
  `group_id` char(32) NOT NULL,
  `mime_type` varchar(64) DEFAULT NULL,
  `size_bytes` bigint(20) unsigned DEFAULT NULL,
  `created_by` char(36) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`file_id`),
  KEY `idx_amigos_upload_group` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `analytics_catalogue_daily` (
  `day` char(10) NOT NULL,
  `works_total` int(11) NOT NULL DEFAULT 0,
  `works_with_usable` int(11) NOT NULL DEFAULT 0,
  `works_without_usable` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `analytics_consults_daily` (
  `day` char(10) NOT NULL,
  `work_id` varchar(64) NOT NULL,
  `provider` varchar(64) NOT NULL DEFAULT '',
  `format` varchar(32) NOT NULL DEFAULT '',
  `consults` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`,`work_id`,`provider`,`format`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `analytics_downloads` (
  `day` char(10) NOT NULL,
  `user_id` varchar(64) NOT NULL,
  `provider` varchar(64) NOT NULL,
  `work_id` varchar(64) NOT NULL DEFAULT '',
  `format` varchar(32) NOT NULL DEFAULT '',
  `quantity` int(11) NOT NULL DEFAULT 0,
  `bytes` bigint(20) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`,`user_id`,`provider`,`work_id`,`format`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `analytics_provider_daily` (
  `day` char(10) NOT NULL,
  `provider` varchar(64) NOT NULL,
  `consults` int(11) NOT NULL DEFAULT 0,
  `downloads` int(11) NOT NULL DEFAULT 0,
  `downloads_failed` int(11) NOT NULL DEFAULT 0,
  `osap_acquired` int(11) NOT NULL DEFAULT 0,
  `osap_failed` int(11) NOT NULL DEFAULT 0,
  `bytes` bigint(20) NOT NULL DEFAULT 0,
  `usable` int(11) NOT NULL DEFAULT 0,
  `unusable` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`,`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `analytics_search_daily` (
  `day` char(10) NOT NULL,
  `total` int(11) NOT NULL DEFAULT 0,
  `with_results` int(11) NOT NULL DEFAULT 0,
  `without_results` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `app_config` (
  `key` varchar(128) NOT NULL,
  `value` text NOT NULL,
  `updated_at` varchar(64) NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `contribution_artifacts` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `contribution_id` bigint(20) unsigned NOT NULL,
  `file_id` bigint(20) unsigned NOT NULL COMMENT 'osap-storage files.id (id opaco, SIN FK cross-service)',
  `kind` varchar(32) DEFAULT NULL COMMENT 'score|audio|other',
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_contribart_contribution` (`contribution_id`),
  KEY `idx_contribart_file` (`file_id`),
  CONSTRAINT `fk_contribart_contribution` FOREIGN KEY (`contribution_id`) REFERENCES `contributions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `contribution_events` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `contribution_id` bigint(20) unsigned NOT NULL,
  `event_type` varchar(32) NOT NULL COMMENT 'created|submitted|status_changed|relation_added|relation_removed|relation_validated|materialized|withdrawn|note',
  `from_status` varchar(16) DEFAULT NULL,
  `to_status` varchar(16) DEFAULT NULL,
  `relation_id` bigint(20) unsigned DEFAULT NULL,
  `detail_json` longtext DEFAULT NULL,
  `actor` varchar(128) DEFAULT NULL COMMENT 'user id o service:<id>',
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_contribev_contribution` (`contribution_id`,`created_at`),
  CONSTRAINT `fk_contribev_contribution` FOREIGN KEY (`contribution_id`) REFERENCES `contributions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `contribution_relations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `contribution_id` bigint(20) unsigned NOT NULL,
  `relation_kind` varchar(16) NOT NULL COMMENT 'musical|contribution',
  `relation_code` varchar(32) NOT NULL COMMENT 'musical: slug de roles; contribution: aportante|propietario_comparte|fuente_declarada',
  `person_id` char(36) DEFAULT NULL COMMENT 'osap-storage persons_id (id opaco, sin FK)',
  `person_name` varchar(512) DEFAULT NULL,
  `validation_status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending|accepted|rejected (eje musical)',
  `validated_by` varchar(128) DEFAULT NULL,
  `validated_at` datetime(6) DEFAULT NULL,
  `materialized` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_contribrel_contribution` (`contribution_id`),
  KEY `idx_contribrel_validation` (`relation_kind`,`validation_status`),
  CONSTRAINT `fk_contribrel_contribution` FOREIGN KEY (`contribution_id`) REFERENCES `contributions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `contributions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `actor_user_id` char(36) NOT NULL COMMENT 'osap-auth users.id (id opaco)',
  `operation` varchar(32) NOT NULL COMMENT 'create_work|add_representation|add_resource (nucleo aditivo, cerrado)',
  `target_kind` varchar(16) NOT NULL COMMENT 'work|representation|resource',
  `target_id` varchar(64) DEFAULT NULL COMMENT 'id en osap-storage. Para add_resource = representation_id. El id de fichero NO va aqui (ver contribution_artifacts)',
  `declared_source` varchar(512) DEFAULT NULL COMMENT 'fuente declarada por el usuario',
  `payload_json` longtext DEFAULT NULL COMMENT 'metadatos declarados (create_work/add_representation): title/origin/type/license/source_name',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft|submitted|in_review|accepted|rejected|withdrawn',
  `reviewed_by` varchar(128) DEFAULT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `review_note` varchar(512) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT current_timestamp(6),
  `updated_at` datetime(6) NOT NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  PRIMARY KEY (`id`),
  KEY `idx_contrib_actor` (`actor_user_id`),
  KEY `idx_contrib_status` (`status`),
  KEY `idx_contrib_target` (`target_kind`,`target_id`),
  KEY `idx_contrib_actor_created` (`actor_user_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `correction_requests` (
  `id` varchar(64) NOT NULL,
  `kind` varchar(32) NOT NULL,
  `entity_id` varchar(255) DEFAULT NULL,
  `entity_provider` varchar(128) DEFAULT NULL,
  `field` varchar(128) DEFAULT NULL,
  `current_value` varchar(1024) DEFAULT NULL,
  `proposed_value` varchar(1024) DEFAULT NULL,
  `message` text NOT NULL,
  `contact_email` varchar(255) DEFAULT NULL,
  `requested_by` varchar(255) DEFAULT NULL,
  `requested_by_name` varchar(255) DEFAULT NULL,
  `requested_by_email` varchar(255) DEFAULT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'pending',
  `admin_message` text DEFAULT NULL,
  `created_at` varchar(64) NOT NULL,
  `decided_at` varchar(64) DEFAULT NULL,
  `decided_by` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `download_plans` (
  `name` varchar(32) NOT NULL,
  `downloads_per_day` int(11) NOT NULL,
  `valid_from` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `download_quota_daily` (
  `day` char(10) NOT NULL,
  `identity_key` varchar(128) NOT NULL,
  `used` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`day`,`identity_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `download_usage` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `day` char(10) NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `work_id` varchar(64) DEFAULT NULL,
  `resource_id` bigint(20) unsigned DEFAULT NULL,
  `provider` varchar(32) NOT NULL,
  `format` varchar(32) DEFAULT NULL,
  `counts_against_plan` tinyint(4) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `idx_usage_day` (`day`),
  KEY `idx_usage_user` (`user_id`,`day`),
  KEY `idx_usage_ip` (`ip_address`,`day`)
) ENGINE=InnoDB AUTO_INCREMENT=64016 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `funnel_events` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `day` char(10) NOT NULL,
  `event` varchar(32) NOT NULL,
  `stage` varchar(8) DEFAULT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `override_id` bigint(20) unsigned DEFAULT NULL,
  `detail` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`detail`)),
  PRIMARY KEY (`id`),
  KEY `idx_funnel_day` (`day`),
  KEY `idx_funnel_event_day` (`event`,`day`),
  KEY `idx_funnel_user` (`user_id`,`day`)
) ENGINE=InnoDB AUTO_INCREMENT=338713 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `index_id_aliases` (
  `old_id` bigint(20) unsigned NOT NULL,
  `new_id` bigint(20) unsigned NOT NULL,
  `method` varchar(32) NOT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`old_id`),
  KEY `ix_index_id_aliases_new` (`new_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `index_representations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `work_id` bigint(20) unsigned NOT NULL,
  `provider` varchar(64) NOT NULL,
  `format` varchar(32) NOT NULL,
  `download_url` text DEFAULT NULL,
  `title_provider` varchar(1024) DEFAULT NULL,
  `available` tinyint(4) NOT NULL DEFAULT 0,
  `quality` tinyint(4) NOT NULL DEFAULT 0,
  `content_hash` char(64) DEFAULT NULL,
  `xml_title` varchar(512) DEFAULT NULL,
  `xml_composer` varchar(255) DEFAULT NULL,
  `source_rep_id` varchar(64) NOT NULL DEFAULT '',
  `resource_id` bigint(20) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_idxrep` (`work_id`,`provider`,`source_rep_id`,`resource_id`,`format`,`title_provider`(255)),
  KEY `idx_idxrep_work` (`work_id`),
  KEY `idx_rep_content_hash` (`content_hash`),
  KEY `ix_new_source` (`provider`,`source_rep_id`),
  KEY `ix_current_url` (`provider`,`download_url`(191))
) ENGINE=InnoDB AUTO_INCREMENT=71422101 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `index_work_voicings` (
  `work_id` bigint(20) unsigned NOT NULL,
  `kind` varchar(16) NOT NULL DEFAULT 'cpdl',
  `term` varchar(64) NOT NULL,
  PRIMARY KEY (`work_id`,`kind`,`term`),
  KEY `idx_work_voicing_term` (`term`,`kind`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `index_works` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `title` varchar(1024) NOT NULL,
  `title_key` varchar(255) NOT NULL,
  `composer_name` varchar(255) DEFAULT NULL,
  `person_id` varchar(36) DEFAULT NULL,
  `catalogue` varchar(255) DEFAULT NULL,
  `catalogue_key` varchar(128) DEFAULT NULL,
  `year` smallint(6) DEFAULT NULL,
  `instrumentation` varchar(255) DEFAULT NULL,
  `source_count` tinyint(4) NOT NULL DEFAULT 0,
  `updated_at` varchar(64) NOT NULL,
  `genre_id` int(11) DEFAULT NULL,
  `public_id` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_idx_public_id` (`public_id`),
  UNIQUE KEY `uq_idx_title_composer` (`title_key`(191),`person_id`),
  KEY `idx_idx_composer` (`person_id`),
  KEY `idx_idx_catalogue` (`catalogue_key`),
  KEY `idx_idx_title` (`title_key`),
  KEY `idx_idx_composer_name` (`composer_name`),
  KEY `idx_idx_updated_at` (`updated_at`,`id`),
  FULLTEXT KEY `ft_idx_title_composer` (`title`,`composer_name`)
) ENGINE=InnoDB AUTO_INCREMENT=410127 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `legacy_index_map` (
  `old_id` bigint(20) unsigned NOT NULL,
  `new_id` bigint(20) unsigned DEFAULT NULL,
  `method` varchar(32) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`old_id`),
  KEY `ix_legacy_index_map_new` (`new_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `legacy_index_representations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `work_id` bigint(20) unsigned NOT NULL,
  `provider` varchar(64) NOT NULL,
  `format` varchar(32) NOT NULL,
  `download_url` text DEFAULT NULL,
  `title_provider` varchar(1024) DEFAULT NULL,
  `available` tinyint(4) NOT NULL DEFAULT 0,
  `quality` tinyint(4) NOT NULL DEFAULT 0,
  `content_hash` char(64) DEFAULT NULL,
  `xml_title` varchar(512) DEFAULT NULL,
  `xml_composer` varchar(255) DEFAULT NULL,
  `source_rep_id` varchar(64) NOT NULL DEFAULT '',
  `resource_id` bigint(20) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_idxrep` (`work_id`,`provider`,`source_rep_id`,`resource_id`,`format`,`title_provider`(255)),
  KEY `idx_idxrep_work` (`work_id`),
  KEY `idx_rep_content_hash` (`content_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=1228943 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `legacy_index_work_voicings` (
  `work_id` bigint(20) unsigned NOT NULL,
  `kind` varchar(16) NOT NULL DEFAULT 'cpdl',
  `term` varchar(64) NOT NULL,
  PRIMARY KEY (`work_id`,`kind`,`term`),
  KEY `idx_work_voicing_term` (`term`,`kind`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `legacy_index_works` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `title` varchar(1024) NOT NULL,
  `title_key` varchar(255) NOT NULL,
  `composer_name` varchar(255) DEFAULT NULL,
  `person_id` varchar(36) DEFAULT NULL,
  `catalogue` varchar(255) DEFAULT NULL,
  `catalogue_key` varchar(128) DEFAULT NULL,
  `year` smallint(6) DEFAULT NULL,
  `instrumentation` varchar(255) DEFAULT NULL,
  `source_count` tinyint(4) NOT NULL DEFAULT 0,
  `updated_at` varchar(64) NOT NULL,
  `genre_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_idx_title_composer` (`title_key`(191),`person_id`),
  KEY `idx_idx_composer` (`person_id`),
  KEY `idx_idx_catalogue` (`catalogue_key`),
  KEY `idx_idx_title` (`title_key`),
  KEY `idx_idx_composer_name` (`composer_name`),
  KEY `idx_idx_updated_at` (`updated_at`,`id`),
  FULLTEXT KEY `ft_idx_title_composer` (`title`,`composer_name`)
) ENGINE=InnoDB AUTO_INCREMENT=809768 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `notifications` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` char(36) DEFAULT NULL,
  `kind` varchar(32) NOT NULL,
  `title` varchar(200) NOT NULL,
  `body` text NOT NULL,
  `link` varchar(500) DEFAULT NULL,
  `created_at` varchar(64) NOT NULL,
  `read_at` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_notifications_user` (`user_id`,`read_at`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `provider_results` (
  `id` varchar(64) NOT NULL,
  `session_id` varchar(64) NOT NULL,
  `provider` varchar(64) NOT NULL,
  `pagination_kind` varchar(16) NOT NULL,
  `cursor_value` varchar(512) NOT NULL,
  `next_cursor` varchar(512) DEFAULT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'fetched',
  `payload_json` mediumtext DEFAULT NULL,
  `meta_json` text DEFAULT NULL,
  `acquired_at` varchar(64) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pr_cursor` (`session_id`,`provider`,`cursor_value`),
  KEY `idx_pr_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `providers` (
  `provider_id` varchar(128) NOT NULL,
  `name` varchar(255) NOT NULL,
  `kind` varchar(32) NOT NULL DEFAULT 'dynamic',
  `base_url` varchar(1024) DEFAULT NULL,
  `wired` tinyint(4) NOT NULL DEFAULT 0,
  `config` text NOT NULL,
  `created_at` varchar(64) NOT NULL,
  `description` text DEFAULT NULL,
  `endpoints` text DEFAULT NULL,
  `mapping` text DEFAULT NULL,
  `resources` text DEFAULT NULL,
  `transforms` text DEFAULT NULL,
  PRIMARY KEY (`provider_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `resolution_items` (
  `id` varchar(64) NOT NULL,
  `session_id` varchar(64) NOT NULL,
  `ref_json` text NOT NULL,
  `status` varchar(32) NOT NULL,
  `resolution_stage` varchar(16) NOT NULL DEFAULT 'provisional',
  `revision` int(11) NOT NULL DEFAULT 1,
  `normalized_json` text DEFAULT NULL,
  `resolved_json` text DEFAULT NULL,
  `confidence` decimal(6,5) NOT NULL DEFAULT 0.00000,
  `candidates_json` text DEFAULT NULL,
  `evidence_json` text DEFAULT NULL,
  `updated_at` varchar(64) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ri_session` (`session_id`),
  KEY `idx_ri_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `resolution_sessions` (
  `session_id` varchar(64) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'acquiring',
  `query_json` text NOT NULL,
  `providers_json` text NOT NULL,
  `policy_json` text NOT NULL,
  `progress_json` text NOT NULL,
  `error` text DEFAULT NULL,
  `created_at` varchar(64) NOT NULL,
  `updated_at` varchar(64) NOT NULL,
  `expires_at` varchar(64) NOT NULL,
  `selection_json` text DEFAULT NULL,
  PRIMARY KEY (`session_id`),
  KEY `idx_rs_status` (`status`),
  KEY `idx_rs_updated` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `source_suggestions` (
  `id` varchar(64) NOT NULL,
  `name` varchar(255) NOT NULL,
  `type` varchar(64) NOT NULL,
  `location` varchar(1024) NOT NULL,
  `mapping` text NOT NULL,
  `requested_by` varchar(255) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'pending',
  `admin_message` text DEFAULT NULL,
  `created_at` varchar(64) NOT NULL,
  `decided_at` varchar(64) DEFAULT NULL,
  `decided_by` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `sync_state` (
  `key` varchar(64) NOT NULL,
  `value` varchar(255) NOT NULL,
  `updated_at` varchar(64) NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `user_quota_overrides` (
  `user_id` varchar(64) NOT NULL,
  `downloads_per_day` int(11) NOT NULL,
  `valid_from` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  `note` varchar(255) DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `work_selections` (
  `work_id` varchar(128) NOT NULL,
  `selection_json` text NOT NULL,
  `updated_at` varchar(64) NOT NULL,
  PRIMARY KEY (`work_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

