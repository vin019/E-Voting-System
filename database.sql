CREATE DATABASE e_voting_system;

USE e_voting_system;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL
);

CREATE TABLE candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    position VARCHAR(100) NOT NULL
);

CREATE TABLE votes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    voter VARCHAR(50) NOT NULL,
    candidate VARCHAR(100) NOT NULL,
    FOREIGN KEY (candidate) REFERENCES candidates(name)
);
