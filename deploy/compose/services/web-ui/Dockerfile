FROM node:lts-alpine3.18

WORKDIR /app

COPY --chown=node:node web-ui/package.json package.json
RUN npm install --no-package-lock && \
    chown node:node -R node_modules && \
    chmod +x -R node_modules/

COPY --chown=node:node web-ui .

EXPOSE 8080

CMD ["npm", "start", "--", "--catalogTitle=\"SharingHUB\"", "--gitlabUrl=\"https://gitlab.si.c-s.fr\"", "--historyMode=\"hash\"", "--pathPrefix=\"/ui\"" ]
