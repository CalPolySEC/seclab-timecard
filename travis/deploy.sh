#!/bin/bash
set -e
eval "$(ssh-agent -s)"
chmod 700 travis
openssl aes-256-cbc -K $encrypted_509c4c4decd3_key -iv $encrypted_509c4c4decd3_iv -in travis/deploy_rsa.enc -out travis/deploy_rsa -d
chmod 600 travis/deploy_rsa
ssh-add travis/deploy_rsa
mkdir -m 700 -p ~/.ssh
echo -e "Host *\n\tStrictHostKeyChecking no\n" > ~/.ssh/config
git remote add deploy "git@thewhitehat.club:seclab-timecard"
PUSH="$(git push deploy master 2>&1)"
echo "$PUSH"
echo "$PUSH" | grep -q "SUCCESS"
