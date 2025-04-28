-- MySQL dump 10.16  Distrib 10.1.37-MariaDB, for Win32 (AMD64)
--
-- Host: localhost    Database: feishu_bot
-- ------------------------------------------------------
-- Server version	10.1.37-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `feishu_bot`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `feishu_bot` /*!40100 DEFAULT CHARACTER SET utf8mb4 */;

USE `feishu_bot`;

--
-- Table structure for table `certificate`
--

DROP TABLE IF EXISTS `certificate`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `certificate` (
  `period_id` int(11) DEFAULT NULL,
  `nickname` varchar(50) DEFAULT NULL,
  `cer_content` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `certificate`
--

LOCK TABLES `certificate` WRITE;
/*!40000 ALTER TABLE `certificate` DISABLE KEYS */;
INSERT INTO `certificate` VALUES (1,'测试','哇塞！王五同学迈出了第一步，创建账号啦！? 这可是通往1k粉丝的起点哦！虽然历史打卡还是空白，但今天就是你的“从零到一”时刻！? 继续加油，未来的网红就是你啦！?✨ 期待你的下一次打卡，让我们一起见证你的成长！??'),(1,'李四','在为期21天的2025-04学习活动中，李四在后端开发领域展现出了非凡的学习热情与专注度。完成了1/21次打卡，迈出了技术成长的重要一步，在项目攻坚方面取得了实质性进展。\n\n- ? 开源组件库开发目标刚起步，首次完成市场分析，决定开发生成废话工具，迈出关键第一步！\n\n? 你已迈出了重要的几步！每一次打卡都是成长的见证，期待下一期活动中你的精彩表现！'),(1,'张三','在为期21天的2025-04学习活动中，张三在Web开发领域展现出了非凡的学习热情与专注度。完成了1/21次打卡，迈出了技术成长的重要一步，在项目攻坚方面取得了实质性进展。\n\n- ? 购物网站开发目标刚起步，已用cursor搭建了vue项目，迈出了第一步！\n\n? 你已迈出了重要的几步！每一次打卡都是成长的见证，期待下一期活动中你的精彩表现！'),(1,'王五','在为期21天的2025-04学习活动中，王五在运营领域展现出了非凡的学习热情与专注度。完成了1/21次打卡，迈出了技术成长的重要一步，在能力拓展方面取得了实质性进展。\n\n- ? 1k粉丝量目标刚起步，首个视频火爆，粉丝猛增2.300个，势头强劲！\n\n? 你已迈出了重要的几步！每一次打卡都是成长的见证，期待下一期活动中你的精彩表现！');
/*!40000 ALTER TABLE `certificate` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `checkins`
--

DROP TABLE IF EXISTS `checkins`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `checkins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `signup_id` int(11) NOT NULL,
  `nickname` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `checkin_date` date NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `checkin_count` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_checkin_signup` (`signup_id`),
  CONSTRAINT `fk_checkin_signup` FOREIGN KEY (`signup_id`) REFERENCES `signups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `checkins`
--

LOCK TABLES `checkins` WRITE;
/*!40000 ALTER TABLE `checkins` DISABLE KEYS */;
INSERT INTO `checkins` VALUES (10,3,'张三','2025-04-27','用cursor搭建了vue项目',1,'2025-04-27 22:09:15'),(11,2,'李四','2025-04-27','做了市场分析决定做一下生成废话的工具',1,'2025-04-27 22:11:15'),(12,4,'王五','2025-04-27','我发了第一个视频，点赞就有快1万了，粉丝一下多了2.300个',1,'2025-04-27 22:12:14');
/*!40000 ALTER TABLE `checkins` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Temporary table structure for view `period_stats`
--

DROP TABLE IF EXISTS `period_stats`;
/*!50001 DROP VIEW IF EXISTS `period_stats`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `period_stats` (
  `period_name` tinyint NOT NULL,
  `nickname` tinyint NOT NULL,
  `checkin_count` tinyint NOT NULL,
  `last_checkin_date` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `periods`
--

DROP TABLE IF EXISTS `periods`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `periods` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `period_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` datetime NOT NULL,
  `end_date` datetime NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `signup_link` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period_name` (`period_name`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `periods`
--

LOCK TABLES `periods` WRITE;
/*!40000 ALTER TABLE `periods` DISABLE KEYS */;
INSERT INTO `periods` VALUES (1,'2025-04','2025-04-24 21:58:21','2025-05-27 21:58:21','已结束','https://hackathonweekly.feishu.cn/base/IFYfbFbG5auTt1s22o7cPWLynmg?ccm_open_type=im_card_automation_link');
/*!40000 ALTER TABLE `periods` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `signups`
--

DROP TABLE IF EXISTS `signups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `signups` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `period_id` int(11) NOT NULL,
  `nickname` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `focus_area` text COLLATE utf8mb4_unicode_ci,
  `introduction` text COLLATE utf8mb4_unicode_ci,
  `goals` text COLLATE utf8mb4_unicode_ci,
  `signup_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `period_nickname` (`period_id`,`nickname`),
  CONSTRAINT `fk_signup_period` FOREIGN KEY (`period_id`) REFERENCES `periods` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `signups`
--

LOCK TABLES `signups` WRITE;
/*!40000 ALTER TABLE `signups` DISABLE KEYS */;
INSERT INTO `signups` VALUES (2,1,'李四','java','java开发经验，热爱开源','完成一个开源组件库的开发','2025-04-24 22:02:38'),(3,1,'张三','前端','前端开发经验，热爱开源','完成一个购物网站的开发','2025-04-24 22:02:38'),(4,1,'王五','运营','小红书博主','达到1k粉丝量','2025-04-24 22:02:38');
/*!40000 ALTER TABLE `signups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Current Database: `feishu_bot`
--

USE `feishu_bot`;

--
-- Final view structure for view `period_stats`
--

/*!50001 DROP TABLE IF EXISTS `period_stats`*/;
/*!50001 DROP VIEW IF EXISTS `period_stats`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `period_stats` AS select `p`.`period_name` AS `period_name`,`s`.`nickname` AS `nickname`,count(`c`.`id`) AS `checkin_count`,max(`c`.`checkin_date`) AS `last_checkin_date` from ((`periods` `p` join `signups` `s` on((`p`.`id` = `s`.`period_id`))) left join `checkins` `c` on((`s`.`id` = `c`.`signup_id`))) group by `p`.`period_name`,`s`.`nickname` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-04-28 22:05:06
