#!/usr/bin/env ruby
#
# Keystone API monitoring script for Sensu
#
# Copyright © 2014 Christopher Eckhardt
#
# Author: Christopher Eckhardt <djbkd@dreamsofelectricsheep.net>
#
# Released under the same terms as Sensu (the MIT license); see LICENSE
# for details.
#
require 'rubygems' if RUBY_VERSION < '1.9.0'
require 'sensu-plugin/check/cli'
require 'net/http'
require 'net/https'
require 'json'

class CheckKeystoneAPI < Sensu::Plugin::Check::CLI

  option :url, :short     => '-u URL'
  option :tenant, :short  => '-T TENANT'
  option :user, :short    => '-U USERNAME'
  option :pass, :short    => '-P PASSWORD'
  option :timeout, :short => '-t SECONDS', :proc => proc {|a| a.to_i}, :default => 10


  def run
    if config[:url]
      uri = URI.parse(config[:url])
      config[:host] = uri.host
      config[:port] = uri.port
      config[:path] = uri.path + '/tokens'
      config[:ssl]  = uri.scheme == 'https'
    else
      unless config[:host] and config[:path]
        unknown 'No URL specified'
      end
      config[:port] ||= 5000
    end

    begin
      timeout(config[:timeout]) do
        request_token
      end
    rescue Timeout::Error
      critical "Keystone API timed out"
    rescue => e
      critical "Keystone API Connection error: #{e.message}"
    end
  end


  def request_token

    conn = Net::HTTP.new(config[:host], config[:port])

    if config[:ssl]
      conn.use_ssl = true
      conn.verify_mode = OpenSSL::SSL::VERIFY_NONE
    end

    api_request = {
      'auth' => {
        'passwordCredentials' => {
          'username' => config[:user],
          'password' => config[:pass]
        },
        'tenantName' => config[:tenant]
      }
    }.to_json

    req = Net::HTTP::Post.new(config[:path])
    req.body = api_request
    req['Content-Type'] = 'application/json'
    res = conn.start{|http| http.request(req)}

    case res.code
    when /^2/
      ok res.code + res.body
    when /^[45]/
      critical res.code + res.body
    else
      warning res.code + res.body
    end
  end
end
