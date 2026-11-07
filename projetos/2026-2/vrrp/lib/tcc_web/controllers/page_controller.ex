defmodule TccWeb.PageController do
  use TccWeb, :controller

  def home(conn, _params) do
    render(conn, :home)
  end
end
