module.exports = {
  devServer: {
    proxy: {
      "^/api": {
        target:
          "http://" + process.env.API_HOST + ":" + process.env.API_PORT + "/",
      },
    },
  },
};
